from ..backend import Core

import os
import pathlib
import logging
from apiflask import APIFlask, APIBlueprint
from flask import send_from_directory, abort as flask_abort
from flask_socketio import SocketIO

from .routes.Table import Table
from .routes.Settings import Settings
from .routes.Tags import Tags
from .routes.Connections import Connections
from .routes.Log import Log
from .routes.Downloads import Downloads


def API(core:Core):
	# Cartella con il build del frontend React (impostabile via env, default /frontend)
	frontend_folder = pathlib.Path(os.getenv('FRONTEND_FOLDER', '/frontend')).resolve()

	app = APIFlask(
		__name__,
		title='Sonarr-AnimeDownloader',
		version=core.version,
		static_folder=str(frontend_folder) if frontend_folder.is_dir() else None,
		static_url_path='',
	)

	app.config['AUTO_404_RESPONSE'] = False
	app.config['AUTO_VALIDATION_ERROR_RESPONSE'] = False
	app.config['SECRET_KEY'] = 'sonarr-animedownloader'

	socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

	@app.after_request
	def cors(res):
		res.headers['Access-Control-Allow-Origin'] = '*'
		res.headers['Access-Control-Allow-Headers'] = '*'
		res.headers['Access-Control-Allow-Methods'] = '*'
		return res

	api = APIBlueprint('api', __name__, url_prefix='/api', tag='General')

	@api.get("/version")
	def get_version():
		"""
		Restituisce il numero di versione.
		"""
		return {"version": core.version}

	@api.put("/wekeup")
	def put_wekeup():
		"""
		Forza l'avvio di una nuova scansione.
		"""
		if core.wakeUp():
			return {"message": "Scansione avviata."}
		else:
			return {"message": "Scansione in corso."}

	api.register_blueprint(Table(core))
	api.register_blueprint(Settings(core))
	api.register_blueprint(Tags(core))
	api.register_blueprint(Connections(core))
	api.register_blueprint(Log(core))
	api.register_blueprint(Downloads(core))
	app.register_blueprint(api)

	# --- SocketIO: push del log e dei progressi di download ---
	class SocketLogHandler(logging.Handler):
		def emit(self, record):
			try:
				msg = self.format(record)
				socketio.emit('log', msg)
			except Exception:
				pass

	socket_log = SocketLogHandler()
	socket_log.setFormatter(logging.Formatter('%(levelname)-8s %(message)s'))
	core.log.addHandler(socket_log)

	# Hook download progress → socket
	def _emit_download_info(d:dict):
		try:
			socketio.emit('download_info', d)
		except Exception:
			pass
	core.downloader.connectHook(_emit_download_info)

	# Servizio del frontend React, se la build è presente
	if frontend_folder.is_dir():
		@app.route('/')
		def index():
			return send_from_directory(str(frontend_folder), 'index.html')

		@app.route('/<path:filename>')
		def static_files(filename:str):
			file_path = (frontend_folder / filename).resolve()
			# Previene path traversal
			try:
				file_path.relative_to(frontend_folder)
			except ValueError:
				flask_abort(404)
			if file_path.is_file():
				return send_from_directory(str(frontend_folder), filename)
			flask_abort(404)

	# Espongo socketio sull'app per chi la usa con socketio.run(app)
	app.socketio = socketio
	return app
