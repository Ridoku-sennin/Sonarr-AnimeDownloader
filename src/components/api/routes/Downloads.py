from ...backend import Core

from apiflask import APIBlueprint

def Downloads(core:Core) -> APIBlueprint:

	route = APIBlueprint('downloads', __name__, url_prefix='/downloads', tag='Downloads')

	@route.after_request
	def cors(res):
		res.headers['Access-Control-Allow-Origin'] = '*'
		res.headers['Access-Control-Allow-Headers'] = '*'
		res.headers['Access-Control-Allow-Methods'] = '*'
		return res

	@route.get('/')
	def get_downloads():
		"""Restituisce la lista dei download attualmente attivi."""

		return core.downloader.getActiveDownloads()

	return route
