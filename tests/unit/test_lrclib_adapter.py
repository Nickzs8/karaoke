"""Testes unitários para o LrclibAdapter."""

import httpx

from karaoke.adapters.lyrics import LrclibAdapter
from karaoke.domain import LyricsLine

SAMPLE_LRC = """
[ti:Bohemian Rhapsody]
[ar:Queen]
[al:A Night at the Opera]
[00:00.90] Is this the real life?
[00:04.50] Is this just fantasy?
[00:09.10] Caught in a landslide
[00:13.00]
"""


def test_get_lyrics_empty_title_returns_empty_tuple() -> None:
    adapter = LrclibAdapter()
    result = adapter.get_lyrics("")
    assert result == ()

    result_spaces = adapter.get_lyrics("   ")
    assert result_spaces == ()


def test_get_lyrics_exact_match_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/get"
        assert request.url.params["track_name"] == "Bohemian Rhapsody"
        assert request.url.params["artist_name"] == "Queen"
        return httpx.Response(
            200,
            json={
                "id": 1,
                "trackName": "Bohemian Rhapsody",
                "artistName": "Queen",
                "syncedLyrics": SAMPLE_LRC,
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("Bohemian Rhapsody", "Queen")

    assert len(lyrics) == 3
    assert lyrics[0] == LyricsLine(
        start_time=0.9, end_time=4.5, text="Is this the real life?"
    )
    assert lyrics[1] == LyricsLine(
        start_time=4.5, end_time=9.1, text="Is this just fantasy?"
    )
    assert lyrics[2] == LyricsLine(
        start_time=9.1, end_time=13.0, text="Caught in a landslide"
    )


def test_get_lyrics_fallback_to_search_when_get_returns_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/get":
            return httpx.Response(404, json={"message": "Not found"})
        if request.url.path == "/api/search":
            assert "Queen Bohemian Rhapsody" in request.url.params["q"]
            return httpx.Response(
                200,
                json=[
                    {"id": 10, "trackName": "Other", "syncedLyrics": None},
                    {
                        "id": 11,
                        "trackName": "Bohemian Rhapsody",
                        "syncedLyrics": (
                            "[00:10.00] Mama, just killed a man\n[00:15.00]"
                        ),
                    },
                ],
            )
        return httpx.Response(400)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("Bohemian Rhapsody", "Queen")

    assert len(lyrics) == 1
    assert lyrics[0] == LyricsLine(
        start_time=10.0, end_time=15.0, text="Mama, just killed a man"
    )


def test_get_lyrics_search_without_artist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search"
        assert request.url.params["q"] == "Imagine"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 20,
                    "syncedLyrics": (
                        "[00:05.00] Imagine there's no heaven\n"
                        "[00:10.00] It's easy if you try"
                    ),
                }
            ],
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client, default_line_duration=4.0)

    lyrics = adapter.get_lyrics("Imagine")

    assert len(lyrics) == 2
    assert lyrics[0] == LyricsLine(
        start_time=5.0, end_time=10.0, text="Imagine there's no heaven"
    )
    # A última linha usa a duração padrão (10.0 + 4.0 = 14.0)
    assert lyrics[1] == LyricsLine(
        start_time=10.0, end_time=14.0, text="It's easy if you try"
    )


def test_get_lyrics_handles_multiple_timestamps_per_line() -> None:
    lrc_with_repeated_timestamps = """
    [00:02.00][00:08.00] Yeah yeah yeah!
    [00:12.00] End
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"syncedLyrics": lrc_with_repeated_timestamps})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client, default_line_duration=3.0)

    lyrics = adapter.get_lyrics("Yeah Song", "Chorus")

    assert len(lyrics) == 3
    assert lyrics[0] == LyricsLine(start_time=2.0, end_time=8.0, text="Yeah yeah yeah!")
    assert lyrics[1] == LyricsLine(
        start_time=8.0, end_time=12.0, text="Yeah yeah yeah!"
    )
    assert lyrics[2] == LyricsLine(start_time=12.0, end_time=15.0, text="End")


def test_get_lyrics_graceful_fallback_when_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not found"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("NonExistentSong", "NonExistentArtist")
    assert lyrics == ()


def test_get_lyrics_graceful_fallback_on_network_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("Any Song", "Any Artist")
    assert lyrics == ()


def test_get_lyrics_graceful_fallback_on_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Not a JSON response")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("Any Song", "Any Artist")
    assert lyrics == ()


def test_get_lyrics_parses_timestamps_with_minutes_and_fractions() -> None:
    lrc_fractions = """
    [01:05.123] Linha em um minuto e cinco
    [01:10.5] Linha com um dígito fracionário
    [02:00] Linha sem fração
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"syncedLyrics": lrc_fractions}])

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics("Time Song")

    assert len(lyrics) == 3
    assert lyrics[0].start_time == 65.123
    assert lyrics[0].end_time == 70.5
    assert lyrics[0].text == "Linha em um minuto e cinco"

    assert lyrics[1].start_time == 70.5
    assert lyrics[1].end_time == 120.0
    assert lyrics[1].text == "Linha com um dígito fracionário"

    assert lyrics[2].start_time == 120.0
    assert lyrics[2].end_time == 124.0
    assert lyrics[2].text == "Linha sem fração"


def test_sanitize_metadata_youtube_noise() -> None:
    adapter = LrclibAdapter()

    title, artist = adapter._sanitize_metadata(
        "Queen - All Dead, All Dead - At Last, the Video!", "Queen Official"
    )
    assert title == "All Dead, All Dead"
    assert artist == "Queen"

    title2, artist2 = adapter._sanitize_metadata(
        "Bohemian Rhapsody [Official Video]", "Queen Topic"
    )
    assert title2 == "Bohemian Rhapsody"
    assert artist2 == "Queen"

    title3, artist3 = adapter._sanitize_metadata(
        "Queen - Don't Stop Me Now (Official Music Video)", "Queen - Topic"
    )
    assert title3 == "Don't Stop Me Now"
    assert artist3 == "Queen"

    title4, artist4 = adapter._sanitize_metadata(
        "Radio Ga Ga (Live Aid 1985)", "QueenVEVO"
    )
    assert title4 == "Radio Ga Ga"
    assert artist4 == "Queen"

    title5, artist5 = adapter._sanitize_metadata(
        "Você pra Sempre (Inveja) - Sandy & Junior (CD Identidade)",
        "Sandy e Junior",
    )
    assert title5 == "Você pra Sempre (Inveja)"
    assert artist5 == "Sandy e Junior"

    # Testes com sufixos típicos de músicas brasileiras
    t_aovivo, a_aovivo = adapter._sanitize_metadata(
        "Chitãozinho & Xororó - Evidências - Ao Vivo em São Paulo",
        "Chitãozinho e Xororó",
    )
    assert t_aovivo == "Evidências"
    assert a_aovivo == "Chitãozinho e Xororó"

    t_clipe, a_clipe = adapter._sanitize_metadata(
        "Exaltasamba - Tá Vendo Aquela Lua - Clipe Oficial", "Exaltasamba"
    )
    assert t_clipe == "Tá Vendo Aquela Lua"

    t_acustico, a_acustico = adapter._sanitize_metadata(
        "Legião Urbana - Pais e Filhos - Acústico MTV", "Legião Urbana"
    )
    assert t_acustico == "Pais e Filhos"

    t_vozviolao, a_vozviolao = adapter._sanitize_metadata(
        "Djavan - Oceano - Voz e Violão", "Djavan"
    )
    assert t_vozviolao == "Oceano"

    t_roda, a_roda = adapter._sanitize_metadata(
        "Thiaguinho - Falta Você - Roda de Samba", "Thiaguinho"
    )
    assert t_roda == "Falta Você"

    t_letra, a_letra = adapter._sanitize_metadata(
        "Alceu Valença - Anunciação - Com Letra", "Alceu Valença"
    )
    assert t_letra == "Anunciação"


def test_get_lyrics_with_youtube_metadata_finds_exact_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/get"
        assert request.url.params["track_name"] == "All Dead, All Dead"
        assert request.url.params["artist_name"] == "Queen"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "trackName": "All Dead, All Dead",
                "artistName": "Queen",
                "syncedLyrics": "[00:10.00] All dead, all dead\n[00:15.00]",
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics(
        title="Queen - All Dead, All Dead - At Last, the Video!",
        artist="Queen Official",
    )
    assert len(lyrics) == 1
    assert lyrics[0].text == "All dead, all dead"
    assert lyrics[0].start_time == 10.0
    assert lyrics[0].end_time == 15.0


def test_get_lyrics_fallback_to_search_with_sanitized_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/get":
            return httpx.Response(404, json={"message": "Not found"})

        if request.url.path == "/api/search":
            query = request.url.params.get("q", "")
            if query == "Queen All Dead, All Dead":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": 100,
                            "trackName": "All Dead, All Dead",
                            "artistName": "Queen",
                            "syncedLyrics": "[00:20.00] In time it comes\n[00:25.00]",
                        }
                    ],
                )
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics(
        title="Queen - All Dead, All Dead - At Last, the Video!",
        artist="Queen Official",
    )
    assert len(lyrics) == 1
    assert lyrics[0].text == "In time it comes"
    assert lyrics[0].start_time == 20.0
    assert lyrics[0].end_time == 25.0


def test_get_lyrics_sandy_junior_variation_and_album_noise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Quando requisitar com título limpo e artista exato ou com &
        if request.url.path == "/api/get":
            track = request.url.params.get("track_name")
            artist = request.url.params.get("artist_name")
            if track == "Você pra Sempre (Inveja)" and artist in (
                "Sandy & Junior",
                "Sandy e Junior",
            ):
                return httpx.Response(
                    200,
                    json={
                        "id": 88,
                        "trackName": "Você Pra Sempre (Inveja)",
                        "artistName": "Sandy & Junior",
                        "syncedLyrics": (
                            "[00:19.71] Eu só quero estar no teu pensamento\n"
                            "[00:24.43] Dentro dos teus sonhos e no teu olhar\n"
                            "[00:29.11]"
                        ),
                    },
                )
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LrclibAdapter(client=mock_client)

    lyrics = adapter.get_lyrics(
        title="Você pra Sempre (Inveja) - Sandy & Junior (CD Identidade)",
        artist="Sandy e Junior",
    )
    assert len(lyrics) == 2
    assert lyrics[0].text == "Eu só quero estar no teu pensamento"
    assert lyrics[0].start_time == 19.71
    assert lyrics[0].end_time == 24.43
    assert lyrics[1].text == "Dentro dos teus sonhos e no teu olhar"
    assert lyrics[1].start_time == 24.43
    assert lyrics[1].end_time == 29.11
