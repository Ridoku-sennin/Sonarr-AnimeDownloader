#!/usr/bin/python3
from components import Core, API

import threading

def main():
	# Carico il core
	core = Core()

	# Cario la pagina web (nuovo API + React frontend)
	app = API(core)

	# Avvio la pagina web
	threading.Thread(target=server, args=[app], daemon=True).start()

	# Avvio il programma
	core.start()

	# Attendo che venga sollevata un eccezione non prevista
	core.join()

def server(app):
	# Usa socketio.run se disponibile (push real-time del log)
	socketio = getattr(app, 'socketio', None)
	if socketio:
		socketio.run(app, debug=False, host='0.0.0.0', use_reloader=False, allow_unsafe_werkzeug=True)
	else:
		app.run(debug=False, host='0.0.0.0', use_reloader=False)

if __name__ == '__main__':
	main()