"""
Processador para arquivos IDF do EnergyPlus.

Este módulo é responsável por todas as modificações e manipulações
de arquivos IDF necessárias para as simulações.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, List
import logging

from confortimetro.config import SimulationConfig
from confortimetro.module_type import ModuleType


def read_zone_names(idf_path: str) -> List[str]:
    """Nomes das zonas declaradas no IDF, na ordem em que aparecem.

    Lê o texto direto em vez de usar o eppy: a GUI só quer preencher uma lista
    e carregar pelo eppy exige o IDD do EnergyPlus e alguns segundos.
    """
    try:
        with open(idf_path, "r", encoding="latin-1") as handle:
            text = handle.read()
    except OSError:
        return []

    names, tokens = [], []
    for line in text.splitlines():
        line = line.split("!")[0].strip()
        if not line:
            continue
        for token in line.replace(";", ",").split(","):
            token = token.strip()
            if token:
                tokens.append(token)
        # Um objeto Zone é "Zone" seguido do nome; ZoneHVAC:* e afins não
        # entram porque a comparação é exata.
        while len(tokens) >= 2:
            if tokens[0].lower() == "zone" and tokens[1] not in names:
                names.append(tokens[1])
            tokens.pop(0)
        if line.endswith(";"):
            tokens.clear()
    return names


def _parse_objects(text: str, object_type: str) -> List[tuple]:
    """Objetos de um tipo como `(campos, primeira_linha, última_linha)`.

    Lê o texto do IDF em vez de usar o eppy: carregar pelo eppy exige o IDD do
    EnergyPlus e alguns segundos, e a interface só quer alguns campos. Campos
    vazios são preservados — a posição de cada um é o que dá sentido a eles.
    """
    lines = text.splitlines()
    objects, index = [], 0
    while index < len(lines):
        head = lines[index].split("!")[0].strip()
        if not head:
            index += 1
            continue

        # O tipo é o primeiro token do objeto; o resto segue até o ';'.
        name = head.split(",")[0].split(";")[0].strip()
        start = index
        chunk = ""
        while index < len(lines):
            piece = lines[index].split("!")[0]
            chunk += piece
            if ";" in piece:
                break
            index += 1
        end = index
        index += 1

        if name.lower() != object_type.lower():
            continue
        fields = [field.strip() for field in chunk.split(";")[0].split(",")]
        objects.append((fields[1:], start, end))
    return objects


def _read_text(idf_path: str) -> str:
    """Texto do IDF, ou string vazia se o arquivo não puder ser lido."""
    try:
        with open(idf_path, "r", encoding="latin-1") as handle:
            return handle.read()
    except OSError:
        return ""


# Equipamento que cada módulo precisa ver ligado no IDF, por zona: o prefixo do
# schedule de controle e o nome que o usuário reconhece. O controlador escreve
# nesses schedules a cada timestep; se nenhum objeto do IDF os consome, a
# simulação roda inteira decidindo no vazio.
MODULE_REQUIRED_EQUIPMENT = {
    ModuleType.COMPLETE: (("JANELA", "janela"), ("VENT", "ventilador"),
                          ("AC", "ar-condicionado")),
    ModuleType.CLOSED_WINDOW: (("VENT", "ventilador"), ("AC", "ar-condicionado")),
    ModuleType.WITHOUT_FAN: (("JANELA", "janela"), ("AC", "ar-condicionado")),
    ModuleType.FIXED_AC_WITHOUT_FAN: (("JANELA", "janela"),
                                      ("AC", "ar-condicionado")),
}


def _referenced_names(text: str) -> dict:
    """Quantas vezes cada nome aparece como campo do IDF, em maiúsculas.

    A declaração `Schedule:Constant` conta como uma ocorrência; quem é usado
    por algum objeto aparece pelo menos duas vezes.
    """
    counts = {}
    for line in text.splitlines():
        line = line.split("!")[0]
        for token in line.replace(";", ",").split(","):
            token = token.strip().upper()
            if token:
                counts[token] = counts.get(token, 0) + 1
    return counts


def unwired_equipment(idf_path: str, rooms: List[str],
                      module_type: ModuleType) -> List[str]:
    """Zonas sem o equipamento que o módulo escolhido exige.

    Devolve mensagens prontas para o usuário. Um schedule de controle só está
    ligado a algo se algum outro objeto do IDF o referencia — o processamento
    cria o schedule que faltar, então a existência dele não prova nada.
    """
    counts = _referenced_names(_read_text(idf_path))
    problems = []
    for prefix, label in MODULE_REQUIRED_EQUIPMENT.get(module_type, ()):
        for room in rooms:
            name = f"{prefix}_{room.upper()}"
            if counts.get(name, 0) < 2:
                problems.append(
                    f"Zona '{room}' não tem {label}: nenhum objeto do IDF usa o "
                    f"schedule {name}, exigido pelo módulo {module_type}.")
    return problems


def _idf_objects(idf_path: str, object_type: str) -> List[List[str]]:
    """Campos de cada objeto de um tipo, lendo o texto do IDF."""
    return [fields for fields, _, _ in
            _parse_objects(_read_text(idf_path), object_type)]


# Posição de cada campo do objeto `People` que a interface edita (IDD 9.4).
PEOPLE_FIELDS = {
    "name": 0,
    "zone": 1,
    "schedule": 2,
    "method": 3,
    "people": 4,
    "people_per_area": 5,
    "area_per_person": 6,
}
PEOPLE_METHODS = ("People", "People/Area", "Area/Person")
# Qual campo cada método de cálculo usa.
PEOPLE_METHOD_FIELD = {
    "people": "people",
    "people/area": "people_per_area",
    "area/person": "area_per_person",
}


def read_people(idf_path: str) -> List[dict]:
    """Objetos `People` do IDF, na ordem em que aparecem.

    Cada item traz os campos de `PEOPLE_FIELDS` mais o `index` do objeto, que
    é o que `write_idf_fields` usa para endereçá-lo.
    """
    people = []
    for index, fields in enumerate(_idf_objects(idf_path, "People")):
        entry = {"index": index}
        for key, position in PEOPLE_FIELDS.items():
            entry[key] = fields[position] if position < len(fields) else ""
        people.append(entry)
    return people


def _serialize_object(object_type: str, fields: List[str]) -> List[str]:
    """Objeto IDF em linhas, uma por campo.

    Os comentários de campo do objeto reescrito se perdem — o resto do arquivo
    sai intacto, porque só as linhas dele são trocadas.
    """
    lines = [f"{object_type},"]
    for position, value in enumerate(fields):
        end = ";" if position == len(fields) - 1 else ","
        lines.append(f"    {value}{end}")
    return lines


def write_idf_fields(src_path: str, dst_path: str, updates: dict) -> None:
    """Copia o IDF trocando alguns campos.

    `updates` mapeia `(tipo, índice do objeto)` para `{posição: valor}`, como
    em `{("Timestep", 0): {0: "6"}}`. O arquivo de origem não é tocado.
    """
    text = _read_text(src_path)
    if not text:
        raise OSError(f"IDF ilegível: {src_path}")

    lines = text.splitlines()
    replacements = {}
    for (object_type, index), changes in updates.items():
        objects = _parse_objects(text, object_type)
        if index >= len(objects):
            raise IndexError(f"{object_type}[{index}] não existe em {src_path}")
        fields, start, end = objects[index]
        for position, value in changes.items():
            while len(fields) <= position:
                fields.append("")
            fields[position] = value
        replacements[start] = (end, _serialize_object(object_type, fields))

    output, index = [], 0
    while index < len(lines):
        if index in replacements:
            end, new_lines = replacements[index]
            output.extend(new_lines)
            index = end + 1
        else:
            output.append(lines[index])
            index += 1

    with open(dst_path, "w", encoding="latin-1") as handle:
        handle.write("\n".join(output) + "\n")


def read_timesteps_per_hour(idf_path: str, default: int = 6) -> int:
    """Valor do objeto `Timestep` do IDF."""
    objects = _idf_objects(idf_path, "Timestep")
    if not objects or not objects[0]:
        return default
    try:
        return int(float(objects[0][0]))
    except ValueError:
        return default


def read_run_period(idf_path: str, default_year: int = 2015):
    """Início e fim do `RunPeriod`, como `(datetime, datetime)`.

    O fim é exclusivo — a meia-noite do dia seguinte —, que é como o
    pós-processamento numera os carimbos de tempo.
    """
    objects = _idf_objects(idf_path, "RunPeriod")
    if not objects or len(objects[0]) < 7:
        return (datetime(default_year, 1, 1), datetime(default_year + 1, 1, 1))

    # Campos: nome, mês e dia iniciais, ano inicial, mês e dia finais, ano final.
    _, begin_month, begin_day, begin_year, end_month, end_day, end_year = objects[0][:7]
    try:
        begin_year = int(begin_year) if begin_year else default_year
        end_year = int(end_year) if end_year else begin_year
        start = datetime(begin_year, int(begin_month), int(begin_day))
        end = datetime(end_year, int(end_month), int(end_day)) + timedelta(days=1)
    except ValueError:
        return (datetime(default_year, 1, 1), datetime(default_year + 1, 1, 1))
    return (start, end)


class IDFProcessor:
    """Processador para modificar arquivos IDF do EnergyPlus."""
    
    # Constantes para nomes de schedules
    OUTDOOR_CO2_SCHEDULE_NAME = "Outdoor CO2 Schedule"
    PEOPLE_OBJECT_NAME = "PEOPLE_{}"
    JANELA_SCHEDULE_NAME = "JANELA_{}"
    VENT_SCHEDULE_NAME = "VENT_{}"
    VEL_SCHEDULE_NAME = "VEL_{}"
    AC_SCHEDULE_NAME = "AC_{}"
    DOAS_SCHEDULE_NAME = "DOAS_STATUS_{}"
    TEMP_COOL_AC_SCHEDULE_NAME = "TEMP_COOL_AC_{}"
    TEMP_HEAT_AC_SCHEDULE_NAME = "TEMP_HEAT_AC_{}"
    PMV_SCHEDULE_NAME = "PMV_{}"
    TEMP_OP_SCHEDULE_NAME = "TEMP_OP_{}"
    ADAP_MIN_SCHEDULE_NAME = "ADAP_MIN_{}"
    ADAP_MAX_SCHEDULE_NAME = "ADAP_MAX_{}"
    EM_CONFORTO_SCHEDULE_NAME = "EM_CONFORTO_{}"
    MET_SCHEDULE_NAME = "METABOLISMO"
    WME_SCHEDULE_NAME = "WORK_EF"
    
    def __init__(self, configs: SimulationConfig):
        """
        Inicializar o processador de IDF.
        
        Args:
            configs: Configurações da simulação
        """
        self.configs = configs
        self.logger = logging.getLogger("idf_processor")
        
        # Configurar eppy com o caminho do IDD
        self._setup_eppy()
    
    def _setup_eppy(self):
        """Configurar o eppy com o arquivo IDD do EnergyPlus."""
        try:
            idd_path = os.path.join(self.configs.energy_path, "Energy+.idd")
            if not os.path.exists(idd_path):
                raise FileNotFoundError(f"IDD file not found: {idd_path}")
            
            from eppy.modeleditor import IDF

            IDF.setiddname(idd_path)
            self.logger.info(f"Eppy configured with IDD: {idd_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup eppy: {e}")
            raise
    
    def process_idf(self) -> bool:
        """
        Processar arquivo IDF completo aplicando todas as modificações necessárias.
        
        Returns:
            bool: True se processamento foi bem-sucedido
        """
        try:
            self.logger.info(f"Starting IDF processing: {self.configs.idf_path}")
            
            # Carregar arquivo IDF
            # eppy importado só aqui: custa ~0,4 s e a GUI abre sem ele.
            from eppy.modeleditor import IDF

            idf = IDF(self.configs.idf_path)
            
            # Aplicar modificações em sequência
            idf = self._modify_simulation_name(idf)
            idf = self._modify_existing_schedules(idf)
            idf = self._add_new_schedules(idf)
            idf = self._configure_people_objects(idf)
            idf = self._add_output_variables(idf)
            
            # Salvar arquivo modificado
            idf.save(self.configs.idf_path)
            
            self.logger.info("IDF processing completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"IDF processing failed: {e}")
            raise
    
    def _modify_simulation_name(self, idf: IDF) -> IDF:
        """
        Modificar nome da simulação baseado no diretório de saída.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            if idf.idfobjects.get("RunPeriod"):
                run_period = idf.idfobjects["RunPeriod"][0]
                simulation_name = os.path.basename(os.path.normpath(self.configs.output_path))
                run_period.Name = simulation_name
                self.logger.debug(f"Simulation name set to: {simulation_name}")
            
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to modify simulation name: {e}")
            raise
            return idf
    
    def _modify_existing_schedules(self, idf: IDF) -> IDF:
        """
        Modificar schedules existentes no arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            schedules_modified = 0
            
            for schedule in idf.idfobjects.get("Schedule:Constant", []):
                schedule_name = schedule.Name
                
                # Modificar schedule de metabolismo
                if schedule_name == self.MET_SCHEDULE_NAME:
                    schedule.Schedule_Type_Limits_Name = "Any Number"
                    schedule.Hourly_Value = self.configs.met_as_watts
                    schedules_modified += 1
                    self.logger.debug(f"Modified MET schedule: {self.configs.met_as_watts}")
                
                # Modificar schedule de work efficiency
                elif schedule_name == self.WME_SCHEDULE_NAME:
                    schedule.Schedule_Type_Limits_Name = "Any Number"
                    schedule.Hourly_Value = self.configs.wme
                    schedules_modified += 1
                    self.logger.debug(f"Modified WME schedule: {self.configs.wme}")
                
                # Modificações específicas para módulo FIXED_AC_WITHOUT_FAN
                elif self.configs.module_type == ModuleType.FIXED_AC_WITHOUT_FAN:
                    if self.TEMP_COOL_AC_SCHEDULE_NAME.format("") in schedule_name:
                        schedule.Hourly_Value = self.configs.temp_ac_max
                        schedules_modified += 1
                        self.logger.debug(f"Modified cooling schedule {schedule_name}: {self.configs.temp_ac_max}")
                    
                    elif self.TEMP_HEAT_AC_SCHEDULE_NAME.format("") in schedule_name:
                        schedule.Hourly_Value = self.configs.temp_ac_min
                        schedules_modified += 1
                        self.logger.debug(f"Modified heating schedule {schedule_name}: {self.configs.temp_ac_min}")
            
            self.logger.info(f"Modified {schedules_modified} existing schedules")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to modify existing schedules: {e}")
            return idf
    
    def _add_new_schedules(self, idf: IDF) -> IDF:
        """
        Adicionar novos schedules ao arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            # Adicionar tipos de limite de schedule se não existirem
            self._ensure_schedule_type_limits(idf)
            
            existing_schedules = {
                schedule.Name: schedule
                for schedule in idf.idfobjects.get("Schedule:Constant", [])
            }

            def add_or_update(name, schedule_type, value):
                schedule = existing_schedules.get(name)
                if schedule is None:
                    idf.newidfobject(
                        "Schedule:Constant",
                        Name=name,
                        Schedule_Type_Limits_Name=schedule_type,
                        Hourly_Value=value,
                    )
                    return True
                schedule.Schedule_Type_Limits_Name = schedule_type
                schedule.Hourly_Value = value
                return False

            schedules_added = add_or_update(self.OUTDOOR_CO2_SCHEDULE_NAME, "Any Number", 400)
            
            # Schedules específicos por sala
            for room in self.configs.rooms:
                room_schedules = [
                    (self.JANELA_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.VENT_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.VEL_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.AC_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.DOAS_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.TEMP_COOL_AC_SCHEDULE_NAME.format(room), "Any Number", self.configs.temp_ac_max),
                    (self.TEMP_HEAT_AC_SCHEDULE_NAME.format(room), "Any Number", self.configs.temp_ac_min),
                    (self.PMV_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.TEMP_OP_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.ADAP_MIN_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.ADAP_MAX_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.EM_CONFORTO_SCHEDULE_NAME.format(room), "On/Off", 0)
                ]
                
                for schedule_name, schedule_type, value in room_schedules:
                    schedules_added += add_or_update(schedule_name, schedule_type, value)
            
            # Schedules globais
            global_schedules = [
                (self.MET_SCHEDULE_NAME, "Any Number", self.configs.met_as_watts),
                (self.WME_SCHEDULE_NAME, "Any Number", self.configs.wme)
            ]
            
            for schedule_name, schedule_type, value in global_schedules:
                schedules_added += add_or_update(schedule_name, schedule_type, value)
            
            self.logger.info(f"Added {schedules_added} new schedules")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to add new schedules: {e}")
            return idf
    
    def _ensure_schedule_type_limits(self, idf: IDF):
        """
        Garantir que os tipos de limite de schedule necessários existam.
        
        Args:
            idf: Objeto IDF do eppy
        """
        try:
            # Verificar tipos existentes
            existing_types = {obj.Name for obj in idf.idfobjects.get("ScheduleTypeLimits", [])}
            
            # Tipos necessários
            required_types = [
                ("On/Off", {
                    "Lower_Limit_Value": 0,
                    "Upper_Limit_Value": 1,
                    "Numeric_Type": "DISCRETE",
                    "Unit_Type": "Dimensionless"
                }),
                ("Any Number", {})
            ]
            
            # Adicionar tipos que não existem
            for type_name, params in required_types:
                if type_name not in existing_types:
                    idf.newidfobject("ScheduleTypeLimits", Name=type_name, **params)
                    self.logger.debug(f"Added schedule type limit: {type_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to ensure schedule type limits: {e}")
            raise
    
    def _configure_people_objects(self, idf: IDF) -> IDF:
        """
        Configurar objetos de pessoas no arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            people_configured = 0
            
            for people in idf.idfobjects.get("People", []):
                people.Activity_Level_Schedule_Name = self.MET_SCHEDULE_NAME
                people.Work_Efficiency_Schedule_Name = self.WME_SCHEDULE_NAME
                people.Air_Velocity_Schedule_Name = self.VEL_SCHEDULE_NAME.format(people.Zone_or_ZoneList_Name)
                people_configured += 1
                
                self.logger.debug(f"Configured people object: {people.Name}")
            
            self.logger.info(f"Configured {people_configured} people objects")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to configure people objects: {e}")
            return idf
    
    def _add_output_variables(self, idf: IDF) -> IDF:
        """
        Adicionar variáveis de saída ao arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            # Definir variáveis de saída desejadas
            desired_output_variables = [
                "People Occupant Count",
                "Site Outdoor Air Drybulb Temperature",
                "Zone Mean Radiante Temperature",
                "Zone Operative Temperature",
                "Zone Air Temperature",
                "Zone Air Relative Humidity",
                "Zone Thermal Comfort ASHRAE 55 Adaptative Model Temperature",
                "Zone Thermal Comfort Fanger Model PMV",
                "Zone Thermal Comfort Clothing Value",
                "Zone Air CO2 Concentration",
                "Schedule Value",
                "Zone Packaged Terminal Heat Pump Total Heating Energy",
                "Zone Packaged Terminal Heat Pump Total Cooling Energy",
                "Zone Infiltration Air Change Rate"
            ]
            
            # Verificar variáveis já existentes
            existing_variables = {
                output_var.Variable_Name 
                for output_var in idf.idfobjects.get("Output:Variable", [])
            }
            
            # Adicionar variáveis que não existem
            variables_added = 0
            for variable_name in desired_output_variables:
                if variable_name not in existing_variables:
                    idf.newidfobject(
                        "Output:Variable",
                        Key_Value="*",
                        Variable_Name=variable_name,
                        Reporting_Frequency="Timestep"
                    )
                    variables_added += 1
                    self.logger.debug(f"Added output variable: {variable_name}")
            
            # Adicionar variáveis específicas por sala
            for room in self.configs.rooms:
                idf.newidfobject(
                    "Output:Variable",
                    Key_Value=f"DOAS_{room.upper()} OUTDOOR AIR INLET",
                    Variable_Name="System Node Mass Flow Rate",
                    Reporting_Frequency="Timestep"
                )
                variables_added += 1
                self.logger.debug(f"Added room-specific output variable for: {room}")
            
            self.logger.info(f"Added {variables_added} output variables")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to add output variables: {e}")
            return idf
    
    def validate_idf(self) -> List[str]:
        """
        Validar arquivo IDF antes do processamento.
        
        Returns:
            List[str]: Lista de erros encontrados
        """
        errors = []
        
        try:
            # Verificar se arquivo existe
            if not os.path.exists(self.configs.idf_path):
                errors.append(f"IDF file not found: {self.configs.idf_path}")
                return errors
            
            # Verificar se arquivo IDD existe
            idd_path = os.path.join(self.configs.energy_path, "Energy+.idd")
            if not os.path.exists(idd_path):
                errors.append(f"IDD file not found: {idd_path}")
                return errors
            
            # Tentar carregar o arquivo IDF
            try:
                from eppy.modeleditor import IDF

                idf = IDF(self.configs.idf_path)
                
                # Verificar se tem objetos essenciais
                if not idf.idfobjects.get("Building"):
                    errors.append("No Building object found in IDF")
                
                if not idf.idfobjects.get("Zone"):
                    errors.append("No Zone objects found in IDF")
                
            except Exception as e:
                errors.append(f"Failed to parse IDF file: {e}")

            errors.extend(unwired_equipment(self.configs.idf_path,
                                            self.configs.rooms or [],
                                            self.configs.module_type))
            
        except Exception as e:
            errors.append(f"Validation error: {e}")
        
        return errors
    


def _self_check() -> None:
    """Ida e volta da edição textual, sem EnergyPlus nem eppy."""
    import tempfile

    source = os.path.join("examples", "idf", "SALA", "SALA_PTHP.idf")
    zones = read_zone_names(source)
    with tempfile.TemporaryDirectory() as directory:
        target = os.path.join(directory, "editado.idf")
        write_idf_fields(source, target, {
            ("Timestep", 0): {0: "4"},
            ("RunPeriod", 0): {1: "3", 2: "10", 4: "3", 5: "17"},
            ("People", 0): {PEOPLE_FIELDS["people"]: "12"},
        })
        assert read_timesteps_per_hour(target) == 4
        start, end = read_run_period(target)
        assert (start.month, start.day) == (3, 10), start
        assert (end.month, end.day) == (3, 18), end  # fim exclusivo
        assert read_people(target)[0]["people"] == "12"
        assert read_zone_names(target) == zones

        # Equipamento exigido pelo módulo: o SALA_PTHP tem AC e ventilador
        # ligados; um IDF sem eles precisa reclamar antes de simular.
        assert unwired_equipment(source, zones, ModuleType.CLOSED_WINDOW) == []
        sem_ac = os.path.join(directory, "sem_ac.idf")
        texto = _read_text(source)
        with open(sem_ac, "w", encoding="latin-1") as handle:
            handle.write(texto.replace(f"AC_{zones[0].upper()}", "ALWAYS ON"))
        problemas = unwired_equipment(sem_ac, zones, ModuleType.CLOSED_WINDOW)
        assert len(problemas) == 1 and "ar-condicionado" in problemas[0], problemas
        # O original continua intacto.
        assert read_timesteps_per_hour(source) == 6
    print("ok")


if __name__ == "__main__":
    _self_check()
