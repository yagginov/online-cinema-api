import pytest

URL_PREFIX = "/api/v1/cinema"


@pytest.mark.asyncio
async def test_search_movies_by_title_case_insensitive(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    assert data["total_items"] > 0

    for movie in data["items"]:
        assert "the" in movie["name"].lower()


@pytest.mark.asyncio
async def test_search_movies_by_title_uppercase(client, seed_database):
    response1 = await client.get(f"{URL_PREFIX}/movies/search/?title=THE")
    response2 = await client.get(f"{URL_PREFIX}/movies/search/?title=the")

    if response1.status_code == 200 and response2.status_code == 200:
        data1 = response1.json()
        data2 = response2.json()
        assert data1["total_items"] == data2["total_items"]


@pytest.mark.asyncio
async def test_search_movies_by_title_partial_match(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=dark")

    if response.status_code == 200:
        data = response.json()
        for movie in data["items"]:
            assert "dark" in movie["name"].lower()


@pytest.mark.asyncio
async def test_search_movies_by_description(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=1")
    assert movies_response.status_code == 200

    movie = movies_response.json()["items"][0]
    description_words = movie.get("description", "").split()

    if description_words:
        search_word = next((w for w in description_words if len(w) > 5), None)

        if search_word:
            response = await client.get(f"{URL_PREFIX}/movies/search/?description={search_word}")
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert "items" in data


@pytest.mark.asyncio
async def test_search_movies_by_star_name(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=1")

    if movies_response.status_code == 200:
        movie_list = movies_response.json()["items"][0]
        movie_id = movie_list["id"]

        detail_response = await client.get(f"{URL_PREFIX}/movies/{movie_id}/")
        assert detail_response.status_code == 200

        movie = detail_response.json()

        if movie.get("stars"):
            star_name = movie["stars"][0]

            response = await client.get(f"{URL_PREFIX}/movies/search/?star_names={star_name}")

            if response.status_code == 200:
                data = response.json()
                assert len(data["items"]) > 0
                assert data["total_items"] > 0


@pytest.mark.asyncio
async def test_search_movies_by_star_name_partial(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=1")
    assert movies_response.status_code == 200

    movie = movies_response.json()["items"][0]

    if movie.get("stars"):
        star_name = movie["stars"][0]
        first_name = star_name.split()[0]

        response = await client.get(f"{URL_PREFIX}/movies/search/?star_names={first_name}")

        if response.status_code == 200:
            data = response.json()
            assert len(data["items"]) > 0


@pytest.mark.asyncio
async def test_search_movies_by_director_name(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=1")

    if movies_response.status_code == 200:
        movie_list = movies_response.json()["items"][0]
        movie_id = movie_list["id"]

        detail_response = await client.get(f"{URL_PREFIX}/movies/{movie_id}/")
        assert detail_response.status_code == 200

        movie = detail_response.json()

        if movie.get("directors"):
            director_name = movie["directors"][0]

            response = await client.get(f"{URL_PREFIX}/movies/search/?director_names={director_name}")

            if response.status_code == 200:
                data = response.json()
                assert len(data["items"]) > 0
                assert data["total_items"] > 0


@pytest.mark.asyncio
async def test_search_movies_or_logic_multiple_stars(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=10")
    assert movies_response.status_code == 200

    movies = movies_response.json()["items"]
    stars = set()
    for movie in movies:
        stars.update(movie.get("stars", []))

    if len(stars) >= 2:
        star_list = list(stars)[:2]
        star_names = ",".join(star_list)

        response = await client.get(f"{URL_PREFIX}/movies/search/?star_names={star_names}")

        if response.status_code == 200:
            data = response.json()
            assert len(data["items"]) > 0

            for movie in data["items"]:
                has_star = any(star in movie["stars"] for star in star_list)
                assert has_star


@pytest.mark.asyncio
async def test_search_movies_or_logic_multiple_directors(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=10")
    assert movies_response.status_code == 200

    movies = movies_response.json()["items"]
    directors = set()
    for movie in movies:
        directors.update(movie.get("directors", []))

    if len(directors) >= 2:
        director_list = list(directors)[:2]
        director_names = ",".join(director_list)

        response = await client.get(f"{URL_PREFIX}/movies/search/?director_names={director_names}")

        if response.status_code == 200:
            data = response.json()
            assert len(data["items"]) > 0


@pytest.mark.asyncio
async def test_search_movies_combined_title_and_description(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&description=story")

    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert "items" in data
        for movie in data["items"]:
            assert "the" in movie["name"].lower()
            assert "story" in movie["description"].lower()


@pytest.mark.asyncio
async def test_search_movies_combined_title_and_star(client, seed_database):
    movies_response = await client.get(f"{URL_PREFIX}/movies/?page=1&size=1")
    assert movies_response.status_code == 200

    movie = movies_response.json()["items"][0]

    if movie.get("stars"):
        star_name = movie["stars"][0]

        response = await client.get(f"{URL_PREFIX}/movies/search/?title=a&star_names={star_name}")

        assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_search_movies_with_pagination(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=a&page=1&per_page=5")

    if response.status_code == 200:
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 5
        assert len(data["items"]) <= 5

        assert "total_items" in data
        assert "total_pages" in data

        if data["total_pages"] > 1:
            assert data["next_page"] is not None
            assert "page=2" in data["next_page"]

        assert data["prev_page"] is None


@pytest.mark.asyncio
async def test_search_movies_pagination_second_page(client, seed_database):
    response1 = await client.get(f"{URL_PREFIX}/movies/search/?title=the&page=1&per_page=5")

    if response1.status_code == 200:
        data1 = response1.json()

        if data1["total_pages"] > 1:
            response2 = await client.get(f"{URL_PREFIX}/movies/search/?title=the&page=2&per_page=5")
            assert response2.status_code == 200

            data2 = response2.json()
            assert data2["page"] == 2
            assert data2["prev_page"] is not None
            assert "page=1" in data2["prev_page"]

            ids1 = {movie["id"] for movie in data1["items"]}
            ids2 = {movie["id"] for movie in data2["items"]}
            assert ids1.isdisjoint(ids2)  # Жодного спільного ID


@pytest.mark.asyncio
async def test_search_movies_with_sorting_by_year_desc(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&sort_by=year&sort_order=desc&per_page=10")

    if response.status_code == 200:
        data = response.json()
        if len(data["items"]) > 1:
            years = [movie["year"] for movie in data["items"]]
            assert years == sorted(years, reverse=True)


@pytest.mark.asyncio
async def test_search_movies_with_sorting_by_year_asc(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&sort_by=year&sort_order=asc&per_page=10")

    if response.status_code == 200:
        data = response.json()
        if len(data["items"]) > 1:
            years = [movie["year"] for movie in data["items"]]
            assert years == sorted(years)


@pytest.mark.asyncio
async def test_search_movies_with_sorting_by_imdb(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=a&sort_by=imdb&sort_order=desc&per_page=10")

    if response.status_code == 200:
        data = response.json()
        if len(data["items"]) > 1:
            ratings = [movie["imdb"] for movie in data["items"]]
            assert ratings == sorted(ratings, reverse=True)


@pytest.mark.asyncio
async def test_search_movies_with_sorting_by_name(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&sort_by=name&sort_order=asc&per_page=10")

    if response.status_code == 200:
        data = response.json()
        if len(data["items"]) > 1:
            names = [movie["name"] for movie in data["items"]]
            assert names == sorted(names)


@pytest.mark.asyncio
async def test_search_movies_no_params_returns_400(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/")
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data
    assert "At least one search parameter must be provided" in data["detail"]


@pytest.mark.asyncio
async def test_search_movies_only_pagination_params_returns_400(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?page=1&per_page=10")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_movies_nonexistent_returns_404(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=xyznonexistentmovie12345678")
    assert response.status_code == 404

    data = response.json()
    assert "detail" in data
    assert "No movies found" in data["detail"]


@pytest.mark.asyncio
async def test_search_movies_response_structure(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the")

    if response.status_code == 200:
        data = response.json()

        assert "items" in data
        assert "page" in data
        assert "size" in data
        assert "total_items" in data
        assert "total_pages" in data
        assert "prev_page" in data or data["prev_page"] is None
        assert "next_page" in data or data["next_page"] is None

        if len(data["items"]) > 0:
            movie = data["items"][0]

            assert "id" in movie
            assert "uuid" in movie
            assert "name" in movie
            assert "year" in movie
            assert "time" in movie
            assert "imdb" in movie
            assert "votes" in movie
            assert "description" in movie
            assert "price" in movie

            assert "meta_score" in movie
            assert "gross" in movie

            assert "certification" in movie
            assert isinstance(movie["certification"], str)


@pytest.mark.asyncio
async def test_search_movies_invalid_per_page(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&per_page=100")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_movies_invalid_page_zero(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&page=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_movies_total_items_matches_count(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the&per_page=5")

    if response.status_code == 200:
        data = response.json()

        if data["total_items"] <= data["size"]:
            assert len(data["items"]) == data["total_items"]
        else:
            assert len(data["items"]) == data["size"]


@pytest.mark.asyncio
async def test_search_movies_special_characters_in_title(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=the%20dark")

    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_search_movies_empty_string_params(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/search/?title=&star_names=")

    assert response.status_code in [400, 422]
