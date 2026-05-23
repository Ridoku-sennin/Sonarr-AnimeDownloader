from ..database import Settings
from ..connection import ConnectionsManager, Sonarr
from .Constant import LOGGER
from ..utility import ColoredString as cs

import httpx, re, pathlib, time
import shutil, tenacity
import threading
import animeworld as aw
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from functools import reduce
from typing import Callable, Any, List


class Downloader:
	"""Gestisce il corretto download degli episodi."""

	def __init__(self, settings:Settings, sonarr:Sonarr, connections:ConnectionsManager, folder:pathlib.Path):
		"""
		Args:
		  settings: Impostazioni
		  sonarr: collegamento con Sonarr
		  connections: collegamento con le Connections
		  folder: la cartella di download
		"""

		self.settings = settings
		self.sonarr = sonarr
		self.connections = connections
		self.folder = folder
		self.log = LOGGER
		self.hook = lambda x:None

		self._lock = threading.Lock()
		self._active_downloads: dict[str, dict] = {}

	def connectHook(self, hook:Callable[[dict[str,Any]], None]):
		"""
		Collega la funzione di hook che verrà richiamata svariate volte durante il download per monitorarne il progresso.

		Args:
		  hook: funzione da richiamare durante il download
		"""
		self.hook = hook

	def getActiveDownloads(self) -> list[dict]:
		"""Restituisce lo stato dei download attualmente attivi."""
		with self._lock:
			return list(self._active_downloads.values())

	def download(self, serie:dict):
		"""
		Scarica ogni episodio contenuto nella serie.

		Args:
		  serie: dizionario con le informazioni
		"""

		for season in serie["seasons"]:
			try:
				self.log.info(f"🔎 Ricerca serie '{serie['title']}' stagione {season['number']}.")

				tmp = [aw.Anime(link=x) for x in season["urls"]]

				episodes_str = ", ".join([str(x["episodeNumber"]) for x in season["episodes"]])
				self.log.info(f"🔎 Ricerca episodio {episodes_str}.")

				episodi:List[aw.Episodio] = reduce(self.flattenEpisodes,[x.getEpisodes() for x in tmp], [])

				max_workers = max(1, int(self.settings["MaxParallelDownloads"]))

				with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Download") as executor:
					futures = [
						executor.submit(self._processEpisode, serie, season, episode, episodi)
						for episode in season["episodes"]
					]
					for future in as_completed(futures):
						try:
							future.result()
						except aw.AnimeNotAvailable as e:
							self.log.info(f'⚠️ {e}')
						except (aw.ServerNotSupported, aw.Error404) as e:
							self.log.warning(cs.yellow(f"🆆🅰🆁🅽🅸🅽🅶: {e}"))

			except aw.AnimeNotAvailable as e:
				self.log.info(f'⚠️ {e}')
			except (aw.ServerNotSupported, aw.Error404) as e:
				self.log.warning(cs.yellow(f"🆆🅰🆁🅽🅸🅽🅶: {e}"))

	def _processEpisode(self, serie:dict, season:dict, episode:dict, episodi:list):
		"""Scarica e processa un singolo episodio."""

		ep_label = f"S{episode['seasonNumber']}E{episode['episodeNumber']}"
		title = f'{serie["title"]} - {ep_label}'

		self.log.info("")
		self.log.info(f"⚙️ Verifica se l'episodio {ep_label} è disponibile.")

		# Controllo se è in download su Sonarr
		if self.__isInQueue(episode['id']):
			self.log.info(f"🔒 [{ep_label}] L'episodio è già in download su Sonarr.")
			return

		episodio = None

		if season["number"] == 'absolute':
			# La serie è in formato assoluto
			res = filter(lambda x: x.number == str(episode['absoluteEpisodeNumber']), episodi)
			episodio = next(res, None)
		else:
			# La serie è normale
			res = filter(lambda x: x.number == str(episode['episodeNumber']), episodi)
			episodio = next(res, None)

		if not episodio:
			self.log.info(f"✖️ [{ep_label}] L'episodio NON è ancora uscito.")
			return

		self.log.info(f"✔️ [{ep_label}] L'episodio è disponibile.")
		self.log.warning(f"⏳ Download episodio {ep_label}.")

		def progress_hook(d:dict):
			percentage = d.get("percentage", 0)
			with self._lock:
				if percentage >= 1:
					self._active_downloads.pop(title, None)
				else:
					self._active_downloads[title] = {
						**d,
						"title": title,
						"serie": serie["title"],
						"season": episode["seasonNumber"],
						"episode": episode["episodeNumber"],
					}
			self.hook(d)

		try:
			file = episodio.download(title, self.folder, hook=progress_hook)
		finally:
			with self._lock:
				self._active_downloads.pop(title, None)

		if not file:
			self.log.warning(f"⚠️ [{ep_label}] Errore in fase di download.")
			return

		file = self.folder.joinpath(file)

		self.log.info(f"✔️ [{ep_label}] Dowload Completato.")

		if self.settings["MoveEp"]:
			# Se l'episodio deve essere spostato

			destination = pathlib.Path(serie["path"])
			self.log.warning(f"⏳ Spostamento episodio episodio {ep_label} in {destination}.")
			if not self.__moveFile(file, destination):
				self.log.error(f"✖️ [{ep_label}] Fallito spostamento episodio.")
				return

			self.log.info(f"✔️ [{ep_label}] Episodio spostato.")
			# Dopo aver spostato il file faccio scansionare a Sonarr la serie per trovarlo
			self.log.info(f"⏳ Aggiornamento serie '{serie['title']}'.")
			self.sonarr.commandRescanSeries(serie['id'])

			if self.settings["RenameEp"]:
				# Se l'episodio deve essere rinominato
				self.log.info(f"⏳ [{ep_label}] Rinominando l'episodio.")

				# Aspetto 2s che Sonarr abbia finito di ricaricare la serie
				time.sleep(2)

				# Chiedo a Sonarr di rinominare l'episodio scaricato
				self.__renameFile(episode['id'], serie['id'])

				self.log.info(f"✔️ [{ep_label}] Episodio rinominato.")

		# Invio una notifica tramite Connections
		self.log.info(f'✉️ [{ep_label}] Inviando il messaggio tramite Connections.')
		self.connections.send(f"*Episode Downloaded*\n{serie['title']} - {episode['seasonNumber']}x{episode['episodeNumber']} - {episode['title']}")

	def flattenEpisodes(self, base:list[aw.Episodio], elem:list[aw.Episodio]) -> list[aw.Episodio]:
		"""
		Linearizza la lista di episodi che appartengono a più pagine Animeworld e corregge eventuali problemi.

		Args:
			base: lista contenente il risultato della riduzione
			elem: lista di episodi da aggiungere alla base
		"""

		# numero da aggiungere per rendere consecutivi gli episodi di varie stagioni
		limit = 0 if len(base) == 0 else int(base[-1].number)

		for ep in elem:
			if re.search(r'^\d+$', ep.number) is not None:
				# Se è un episodio intero
				ep.number = str(int(ep.number) + limit)
				base.append(ep)

			elif re.search(r'^\d+\.\d+$', ep.number) is not None:
				# Se è un episodio fratto
				# lo salta perchè sicuramente uno speciale
				continue

			elif re.search(r'^\d+-\d+$', ep.number) is not None:
				# Se è un pisodio doppio
				# Duplica l'episodio
				ep_cpy = deepcopy(ep)

				ep.number = str(int(ep.number.split('-')[0]) + limit)
				ep_cpy.number = str(int(ep.number.split('-')[1]) + limit)

				base.extend([ep,ep_cpy])

		return base

	def __isInQueue(self, episode_id:int) -> bool:
		"""
		Controllo se un episodio è in download su Sonarr.

		Args:
		  episode_id: L'ID dell'episodio.

		Returns:
		  True se è in download su Sonarr, altrimenti False.
		"""

		# Controllo che non sia già in download su sonarr
		res = self.sonarr.queue()
		res.raise_for_status()
		records = res.json()["records"]

		for record in records:
			if episode_id == record["episodeId"]: return True
		return False

	def __moveFile(self, src:pathlib.Path, dst:pathlib.Path) -> pathlib.Path:
		"""
		Sposta il file da src a dst.

		Args:
		  src: file da spostare
		  dst: cartella di destinazione

		Returns:
		  La path che punta al file spostato.
		"""

		if not src.is_file():
			raise FileNotFoundError(src)

		# Controllo se la cartella di destinazione non sia una cartella windows
		if re.match(r"\w:", str(dst)):
			dst = pathlib.PureWindowsPath(dst).as_posix()
			dst = pathlib.PosixPath(re.sub(r"\w:","",dst))

		if not dst.is_dir():
			# Se la cartella non esiste viene creata
			dst.mkdir(parents=True)
			self.log.warning(f'⚠️ La cartella {dst} è stata creata.')

		dst = dst.joinpath(src.name)
		return shutil.move(src,dst)

	@tenacity.retry(reraise=True, stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(2))
	def __renameFile(self, episode_id:int, serie_id:int) -> None:
		"""
		Rinomina il file seguendo la formattazione definita su Sonarr.

		Args:
		  episode_id: id_episodio su Sonarr
		  serie_id: id della serie su Sonarr
		"""

		res = self.sonarr.episode(episode_id)
		res.raise_for_status()
		res = res.json()

		if "episodeFile" not in res: raise Exception("Episodio Non trovato")

		file_id = res["episodeFile"]["id"]
		self.sonarr.commandRenameFiles(serie_id,[file_id])
