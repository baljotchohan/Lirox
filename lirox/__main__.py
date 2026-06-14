"""python -m lirox  |  python -m lirox --web"""
import sys

if "--web" in sys.argv:
    sys.argv.remove("--web")
    from lirox.main_web import main_web
    main_web()
else:
    from lirox.main import main
    main()
