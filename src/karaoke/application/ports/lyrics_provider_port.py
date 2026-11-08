"""Porta de Aplicação: LyricsProviderPort."""

from typing import Protocol

from karaoke.domain import LyricsLine


class LyricsProviderPort(Protocol):
    """Contrato para busca e sincronização de letras no formato LRC."""

    def get_lyrics(
        self, title: str, artist: str | None = None
    ) -> tuple[LyricsLine, ...]:
        """Busca a letra sincronizada e retorna uma sequência ordenada de LyricsLine."""
        ...
