"""main() precisa chamar freeze_support antes da GUI: no .exe do Windows o
ProcessPoolExecutor de recompute_runs relança o próprio executável."""

import multiprocessing

import main as entry


def test_main_chama_freeze_support_antes_da_janela(monkeypatch):
    ordem = []
    monkeypatch.setattr(multiprocessing, "freeze_support", lambda: ordem.append("freeze"))
    monkeypatch.setattr(entry, "resolve_config_path", lambda: "examples/config.json")

    class FakeWindow:
        def __init__(self, config_path):
            ordem.append("window")

        def mainloop(self):
            pass

    monkeypatch.setattr(entry, "MainWindow", FakeWindow)
    entry.main()

    assert ordem == ["freeze", "window"]
