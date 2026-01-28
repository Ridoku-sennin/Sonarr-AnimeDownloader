import httpx
import re
import animeworld as aw
from typing import Optional

from ..core.Constant import LOGGER

class ExternalDB:
	"""
	Collegamento con le informazioni che si trovano su GitHub.
	https://github.com/Fribb/anime-lists
	"""

	def __init__(self):
		self.log = LOGGER
		self.client = httpx.Client()
		self._data = []
	
	def sync(self) -> list:
		"""
		Sincronizza i dati interni con il database esterno.

		Returns:
		  Tutti i dati aggiornati.
		"""

		res = self.client.get("https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json")
		res.raise_for_status()
		self._data = res.json()
		return self._data
	
	def getData(self)-> list:
		"""
		Restituisce tutti i dati.

		Returns:
		  I dati nel database.
		"""
		return list(self._data)
	
	def _generate_title_variations(self, title: str) -> list[str]:
		"""
		Genera varianti del titolo per migliorare la ricerca su AnimeWorld.
		
		Args:
		  title: titolo originale.
		
		Returns:
		  Lista di varianti del titolo (senza duplicati).
		"""
		variations = [title]
		
		# Variante 1: rimuove spazi dopo i due punti (es. "Re: Zero" -> "Re:Zero")
		no_space_after_colon = title.replace(": ", ":")
		if no_space_after_colon != title:
			variations.append(no_space_after_colon)
		
		# Variante 2: rimuove punteggiatura comune
		no_punctuation = re.sub(r'[:,\.!]', '', title)
		no_punctuation = re.sub(r'\s+', ' ', no_punctuation).strip()
		if no_punctuation not in variations:
			variations.append(no_punctuation)
		
		return variations
	
	def _search_with_variations(self, title: str, mal_ids: list[int]) -> list:
		"""
		Cerca su AnimeWorld provando diverse varianti del titolo.
		
		Args:
		  title: titolo dell'anime.
		  mal_ids: lista di MAL ID validi per il match.
		
		Returns:
		  Lista di risultati filtrati, o lista vuota se non trova nulla.
		"""
		variations = self._generate_title_variations(title)
		
		for variant in variations:
			res = aw.find(variant)
			filtered = list(filter(lambda x: x["malId"] in mal_ids and x['language'] == 'jp', res))
			if len(filtered) > 0:
				if variant != title:
					self.log.info(f"Trovato match con variante '{variant}' invece di '{title}'")
				return filtered
		
		return []

	def find(self, title:str, season:int, tvdb_id:int) -> Optional[list[dict[str, str]]]:
		"""
		Cerca gli url per il download di una stagione.

		Args:
		  title: titolo dell'anime.
		  season: stagione dell'anime.
		  tvdb_id: ID di thetvdb.
		
		Returns:
		  Una lista di dizionari con nome e url trovati (può contenere più elementi per split cour).
		  None se non trova nulla.
		"""

		# Ottengo un elenco di ID di MyAnimeList che fanno match per la stagione specifica
		mal_ids = []
		for info in self._data:
			if "tvdb_id" not in info: continue
			if "mal_id" not in info: continue
			if "type" not in info: continue
			if "season" not in info: continue
			if info["tvdb_id"] != tvdb_id: continue
			if info["type"] != "TV": continue
			
			# Filtro per la stagione corretta (gestisce anche split cour)
			if "tvdb" in info["season"] and info["season"]["tvdb"] == season:
				mal_ids.append(info["mal_id"])
		
		# Se non ho trovato nulla ritorno None
		if len(mal_ids) == 0: return None

		# Cerco su AnimeWorld provando diverse varianti del titolo
		res = self._search_with_variations(title, mal_ids)

		# Se non ho trovato nulla, provo con il titolo + numero stagione (es. "Fire Force 3")
		if len(res) == 0 and season > 1:
			self.log.info(f"Nessun risultato con '{title}', provo con '{title} {season}'")
			res = self._search_with_variations(f"{title} {season}", mal_ids)

		# Se non ho trovato nulla ritorno None
		if len(res) == 0: return None

		# Converto le stagioni in numeri
		def convert(x):
			x["year"] = int(x["year"])
			if x["season"] == 'winter':
				x["season"] = 0
			elif x["season"] == 'spring':
				x["season"] = 1
			elif x["season"] == 'summer':
				x["season"] = 2
			else:
				x["season"] = 3
			return x
		res = list(map(convert, res))

		# Riordino per data
		res.sort(key=lambda x: (x["year"], x["season"]))

		# Ritorno tutti i risultati (per split cour saranno entrambe le parti)
		return [
			{
				"name": r["name"],
				"url": r["link"]
			}
			for r in res
		]