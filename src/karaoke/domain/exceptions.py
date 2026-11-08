"""Exceções da camada de Domínio."""


class DomainError(Exception):
    """Exceção base para todos os erros de negócio do domínio."""


class SongNotFoundError(DomainError):
    """Lançada quando uma música não é encontrada no catálogo ou armazenamento."""


class InvalidAudioFormatError(DomainError):
    """Lançada quando um formato de arquivo de áudio não é suportado ou é inválido."""


class InvalidScoreError(DomainError):
    """Lançada quando a pontuação está fora do intervalo permitido (0 a 100)."""


class InvalidLyricsTimeError(DomainError):
    """Lançada quando o tempo de início ou fim de uma linha de letra é inválido."""


class AudioDownloadError(DomainError):
    """Lançada quando ocorre uma falha ao baixar ou extrair áudio."""


class SongNotReadyError(DomainError):
    """Lançada quando uma música é acessada antes de estar pronta para uso."""
