"""Adaptador de Letras Sincronizadas: LrclibAdapter."""

import re
from typing import Any

import httpx

from karaoke.application.ports import LyricsProviderPort
from karaoke.domain import LyricsLine


class LrclibAdapter(LyricsProviderPort):
    """Implementa LyricsProviderPort consumindo a API aberta do LRCLIB.

    Busca letras sincronizadas no formato LRC por título e artista (ou busca ampla).
    Realiza o parsing de timestamps e converte as faixas para LyricsLine.
    Apresenta fallback gracioso caso a letra não seja encontrada ou a rede falhe.
    """

    # Expressão regular para capturar marcadores de tempo no formato LRC:
    # Exemplo de linha LRC: "[01:23.45] Letra da música"
    #
    # Decomposição da regex:
    #   \[               -> Encontra o caractere literal de abertura '['
    #   (\d+)            -> Grupo 1 (minutos): 1 ou mais dígitos (ex: "01", "3", "120")
    #   :                -> Encontra o caractere literal ':' separador de min/seg
    #   (\d{2}(?:\.\d+)?)-> Grupo 2 (segundos):
    #                         \d{2}     : 2 dígitos de segundos (ex: "05", "23")
    #                         (?:\.\d+)?: fração decimal opcional (".45", ".123")
    #   \]               -> Encontra o caractere literal de fechamento ']'
    #
    # O que essa regex casa:
    #   - "[00:15.30]" -> Grupo 1 = "00", Grupo 2 = "15.30"
    #   - "[01:05.123]" -> Grupo 1 = "01", Grupo 2 = "05.123"
    #   - "[02:10]"    -> Grupo 1 = "02", Grupo 2 = "10"
    #
    # O que essa regex NÃO casa (e ignora automaticamente):
    #   - Tags de metadados: "[ar:Queen]", "[ti:Bohemian Rhapsody]", "[al:Album]"
    TIMESTAMP_PATTERN = re.compile(r"\[(\d+):(\d{2}(?:\.\d+)?)\]")

    def __init__(
        self,
        base_url: str = "https://lrclib.net/api",
        user_agent: str = "KaraokeApp/1.0 (https://github.com/Nickzs8/karaoke)",
        timeout_seconds: float = 10.0,
        default_line_duration: float = 4.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.default_line_duration = default_line_duration
        self._custom_client = client

    def get_lyrics(
        self, title: str, artist: str | None = None
    ) -> tuple[LyricsLine, ...]:
        """Orquestra a busca e o parsing da letra sincronizada."""
        clean_title = title.strip()
        clean_artist = artist.strip() if artist else None

        if not clean_title:
            return ()

        synced_lrc = self._fetch_synced_lrc(clean_title, clean_artist)
        if not synced_lrc:
            return ()

        return self._parse_lrc(synced_lrc)

    def _fetch_synced_lrc(self, title: str, artist: str | None) -> str | None:
        """Tenta obter a letra sincronizada via busca exata ou busca textual."""
        clean_title, clean_artist = self._sanitize_metadata(title, artist)

        try:
            with self._create_or_reuse_client() as client:
                title_candidates = self._title_variants(clean_title)
                artist_candidates = self._artist_variants(clean_artist)

                # 1. Correspondência exata tentando variações de título e artista limpos
                for t_cand in title_candidates:
                    for a_cand in artist_candidates:
                        exact_lrc = self._request_exact_match(client, t_cand, a_cand)
                        if exact_lrc:
                            return exact_lrc

                # 2. Correspondência exata com metadados originais (se diferirem)
                if artist and (clean_title != title or clean_artist != artist):
                    exact_lrc = self._request_exact_match(client, title, artist)
                    if exact_lrc:
                        return exact_lrc

                # 3. Busca textual com múltiplas variantes de consulta
                for query in self._build_search_candidates(
                    clean_title, clean_artist, title, artist
                ):
                    search_lrc = self._request_search(client, query)
                    if search_lrc:
                        return search_lrc

                return None
        except (httpx.HTTPError, Exception):
            # Fallback gracioso: qualquer falha de rede/parsing retorna None
            return None

    def _normalize_for_match(self, text: str) -> str:
        """Normaliza texto para comparação fonética/textual de artistas."""
        lowered = text.lower()
        replaced = re.sub(r"&", " e ", lowered)
        replaced = re.sub(r"\band\b", " e ", replaced)
        cleaned = re.sub(r"[^\w\s]", " ", replaced)
        return " ".join(cleaned.split())

    def _artists_match(self, candidate: str, target: str) -> bool:
        """Verifica se dois nomes de artistas coincidem semanticamente."""
        norm_cand = self._normalize_for_match(candidate)
        norm_target = self._normalize_for_match(target)
        if not norm_cand or not norm_target:
            return False
        return norm_cand in norm_target or norm_target in norm_cand

    def _artist_variants(self, artist: str | None) -> list[str]:
        """Gera variações comuns de conectivos em nomes de artistas (&, e, and)."""
        if not artist:
            return []
        variants = [artist]
        if " e " in artist:
            variants.append(re.sub(r"\b e \b", " & ", artist))
            variants.append(re.sub(r"\b e \b", " and ", artist))
        elif " & " in artist:
            variants.append(artist.replace(" & ", " e "))
            variants.append(artist.replace(" & ", " and "))
        elif " and " in artist:
            variants.append(re.sub(r"\band\b", " & ", artist))
            variants.append(re.sub(r"\band\b", " e ", artist))
        return [v.strip() for v in dict.fromkeys(variants) if v.strip()]

    def _title_variants(self, title: str) -> list[str]:
        """Gera variantes do título (com e sem conteúdo entre parênteses)."""
        variants = [title]
        without_parens = re.sub(r"\s*[\(\[\{].*?[\)\]\}]\s*", " ", title).strip()
        if without_parens and without_parens != title:
            variants.append(without_parens)
        return [v.strip() for v in dict.fromkeys(variants) if v.strip()]

    def _sanitize_metadata(
        self, title: str, artist: str | None
    ) -> tuple[str, str | None]:
        """Limpa ruídos e sufixos típicos de títulos e canais do YouTube."""
        clean_artist = artist.strip() if artist else None
        if clean_artist:
            clean_artist = re.sub(
                r"(?i)\s*(?:official|topic|vevo|records|music|channel)\s*$",
                "",
                clean_artist,
            ).strip(" -–—|")
            if not clean_artist:
                clean_artist = None

        clean_title = title.strip()
        # Remove parênteses e colchetes comuns com termos de vídeo ou álbuns
        video_tags_pattern = (
            r"(?i)[\(\[\{](?:official|oficial|top of the pops|\d{4}|video|vídeo"
            r"|videoclipe|vídeoclipe|clipe|clip|webclipe|lyric|letra|com letra"
            r"|legendado|audio|áudio|álbum|album|cd|dvd|remaster|hd|4k|at last"
            r"|live|ao vivo|ensaio|acústico|acustico|acoustic|deluxe|versão|versao"
            r"|version|visualizer|completo|full|voz e violão|voz e violao"
            r"|roda de samba|pagode de mesa|lançamento|lancamento"
            r"|inédita|inedita).*?[\)\]\}]"
        )
        clean_title = re.sub(video_tags_pattern, "", clean_title)

        # Remove sufixos como '- At Last, the Video!' ou '- Ao Vivo em São Paulo'
        suffix_pattern = (
            r"(?i)\s*-\s*(?:at last|official|oficial|video|vídeo|videoclipe"
            r"|vídeoclipe|clipe|clip|webclipe|lyric|lyrics|letra|com letra"
            r"|legendado|audio|áudio|hd|4k|live|ao vivo|acústico|acustico"
            r"|acoustic|ensaio|session|live session|voz e violão|voz e violao"
            r"|só voz e violão|so voz e violao|roda de samba|pagode de mesa"
            r"|versão|versao|version|lançamento|lancamento|música nova|musica nova"
            r"|inédita|inedita|remaster|remasterizado|remasterizada|visualizer"
            r"|cd|dvd|album|álbum|completo|completa|piseiro|forró|forro"
            r"|sertanejo|pagode|samba|funk|brega funk|kondzilla|gr6|love funk"
            r"|remix|extended|medley|pot-pourri|potpourri|pot pourri).*$"
        )
        clean_title = re.sub(suffix_pattern, "", clean_title)

        # Detecta padrão 'Artista - Título' ou 'Título - Artista' no título do vídeo
        if " - " in clean_title:
            parts = clean_title.split(" - ", 1)
            left = parts[0].strip()
            right = parts[1].strip()
            if clean_artist and self._artists_match(left, clean_artist):
                clean_title = right
            elif clean_artist and self._artists_match(right, clean_artist):
                clean_title = left
            elif not clean_artist:
                clean_artist = left
                clean_title = right

        clean_title = clean_title.strip(" -–—|")
        if not clean_title:
            clean_title = title.strip()

        return clean_title, clean_artist

    def _build_search_candidates(
        self,
        clean_title: str,
        clean_artist: str | None,
        raw_title: str,
        raw_artist: str | None,
    ) -> list[str]:
        """Gera lista de consultas de busca textual ordenadas por especificidade."""
        queries: list[str] = []
        title_variants = self._title_variants(clean_title)
        artist_variants = self._artist_variants(clean_artist)

        for a in artist_variants:
            for t in title_variants:
                q = f"{a} {t}".strip()
                if q and q not in queries:
                    queries.append(q)

        for t in title_variants:
            if t not in queries:
                queries.append(t)

        if raw_artist and raw_title:
            raw_combined = f"{raw_artist} {raw_title}".strip()
            if raw_combined and raw_combined not in queries:
                queries.append(raw_combined)

        return queries

    def _create_or_reuse_client(self) -> Any:
        """Retorna o cliente HTTP customizado ou um novo contexto de cliente."""
        if self._custom_client is not None:
            return _ClientContextWrapper(self._custom_client)

        return httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
        )

    def _request_exact_match(
        self, client: httpx.Client, title: str, artist: str
    ) -> str | None:
        """Consulta o endpoint /api/get do LRCLIB com artista e título exatos."""
        response = client.get(
            f"{self.base_url}/get",
            params={"track_name": title, "artist_name": artist},
        )
        if response.status_code == 200:
            data = response.json()
            synced = data.get("syncedLyrics")
            if isinstance(synced, str) and synced.strip():
                return synced.strip()
        return None

    def _request_search(self, client: httpx.Client, query: str) -> str | None:
        """Consulta /api/search do LRCLIB pelo primeiro resultado sincronizado."""
        response = client.get(
            f"{self.base_url}/search",
            params={"q": query},
        )
        if response.status_code == 200:
            results = response.json()
            if isinstance(results, list):
                for item in results:
                    synced = item.get("syncedLyrics")
                    if isinstance(synced, str) and synced.strip():
                        return synced.strip()
        return None

    def _parse_lrc(self, lrc_content: str) -> tuple[LyricsLine, ...]:
        """Realiza o parsing de uma string LRC completa em instâncias de LyricsLine."""
        raw_timed_lines = self._extract_timed_lines(lrc_content)
        if not raw_timed_lines:
            return ()
        return self._build_lyrics_lines(raw_timed_lines)

    def _extract_timed_lines(self, lrc_content: str) -> list[tuple[float, str]]:
        """Extrai timestamps e seus respectivos textos, ordenados cronologicamente."""
        timed_lines: list[tuple[float, str]] = []

        for line in lrc_content.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue

            matches = self.TIMESTAMP_PATTERN.findall(clean_line)
            if not matches:
                continue

            text_content = self.TIMESTAMP_PATTERN.sub("", clean_line).strip()
            for minutes_str, seconds_str in matches:
                timestamp = self._parse_timestamp(minutes_str, seconds_str)
                timed_lines.append((timestamp, text_content))

        timed_lines.sort(key=lambda item: item[0])
        return timed_lines

    def _parse_timestamp(self, minutes_str: str, seconds_str: str) -> float:
        """Converte minutos e segundos em valor float total em segundos."""
        minutes = int(minutes_str)
        seconds = float(seconds_str)
        return round(minutes * 60.0 + seconds, 3)

    def _build_lyrics_lines(
        self, raw_lines: list[tuple[float, str]]
    ) -> tuple[LyricsLine, ...]:
        """Calcula o start_time e end_time de cada linha de texto e gera LyricsLine."""
        parsed_lines: list[LyricsLine] = []
        total_items = len(raw_lines)

        for index, (start_time, text) in enumerate(raw_lines):
            # Linha sem texto atua apenas como marcador temporal de encerramento
            if not text:
                continue

            end_time = self._calculate_end_time(
                index, start_time, raw_lines, total_items
            )

            # Evita inconsistência temporal se o timestamp posterior for inválido
            safe_end_time = max(start_time, end_time)

            parsed_lines.append(
                LyricsLine(
                    start_time=start_time,
                    end_time=safe_end_time,
                    text=text,
                )
            )

        return tuple(parsed_lines)

    def _calculate_end_time(
        self,
        current_index: int,
        start_time: float,
        raw_lines: list[tuple[float, str]],
        total_items: int,
    ) -> float:
        """Determina o fim com base no próximo timestamp ou na duração padrão."""
        if current_index + 1 < total_items:
            next_timestamp = raw_lines[current_index + 1][0]
            if next_timestamp >= start_time:
                return next_timestamp

        return start_time + self.default_line_duration


class _ClientContextWrapper:
    """Wrapper para permitir que clientes reutilizados sejam usados em blocos with."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, *args: Any) -> None:
        # Não fecha o cliente se ele foi injetado de fora
        pass
