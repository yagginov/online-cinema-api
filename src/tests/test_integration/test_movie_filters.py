import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.models import MovieModel, GenreModel, CertificationModel

URL_PREFIX = "/api/v1/cinema"


@pytest.mark.asyncio
async def test_filter_movies_by_year_from(client, db_session, seed_database):
    year_from = 2015

    response = await client.get(f"{URL_PREFIX}/movies/?year_from={year_from}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert movie["year"] >= year_from


@pytest.mark.asyncio
async def test_filter_movies_by_year_to(client, db_session, seed_database):
    year_to = 2020

    response = await client.get(f"{URL_PREFIX}/movies/?year_to={year_to}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert movie["year"] <= year_to


@pytest.mark.asyncio
async def test_filter_movies_by_year_range(client, db_session, seed_database):
    year_from = 2010
    year_to = 2020

    response = await client.get(
        f"{URL_PREFIX}/movies/?year_from={year_from}&year_to={year_to}"
    )
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        assert year_from <= movie["year"] <= year_to


@pytest.mark.asyncio
async def test_filter_movies_invalid_year_range(client, seed_database):
    year_from = 2020
    year_to = 2010

    response = await client.get(
        f"{URL_PREFIX}/movies/?year_from={year_from}&year_to={year_to}"
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "year_from cannot be greater than year_to" in str(response_data["detail"])


@pytest.mark.asyncio
async def test_filter_movies_by_min_imdb(client, db_session, seed_database):
    min_imdb = 7.5

    response = await client.get(f"{URL_PREFIX}/movies/?min_imdb={min_imdb}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert movie["imdb"] >= min_imdb


@pytest.mark.asyncio
async def test_filter_movies_by_max_imdb(client, db_session, seed_database):
    max_imdb = 8.0

    response = await client.get(f"{URL_PREFIX}/movies/?max_imdb={max_imdb}")
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        assert movie["imdb"] <= max_imdb


@pytest.mark.asyncio
async def test_filter_movies_by_imdb_range(client, db_session, seed_database):
    min_imdb = 6.0
    max_imdb = 8.5

    response = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb={min_imdb}&max_imdb={max_imdb}"
    )
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        assert min_imdb <= movie["imdb"] <= max_imdb


@pytest.mark.asyncio
async def test_filter_movies_invalid_imdb_range(client, seed_database):
    min_imdb = 8.0
    max_imdb = 6.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb={min_imdb}&max_imdb={max_imdb}"
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "min_imdb cannot be greater than max_imdb" in str(response_data["detail"])


@pytest.mark.asyncio
async def test_filter_movies_by_min_price(client, db_session, seed_database):
    min_price = 10.0

    response = await client.get(f"{URL_PREFIX}/movies/?min_price={min_price}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert float(movie["price"]) >= min_price


@pytest.mark.asyncio
async def test_filter_movies_by_max_price(client, db_session, seed_database):
    max_price = 15.0

    response = await client.get(f"{URL_PREFIX}/movies/?max_price={max_price}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert float(movie["price"]) <= max_price


@pytest.mark.asyncio
async def test_filter_movies_by_price_range(client, db_session, seed_database):
    min_price = 5.0
    max_price = 15.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?min_price={min_price}&max_price={max_price}"
    )
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        price = float(movie["price"])
        assert min_price <= price <= max_price


@pytest.mark.asyncio
async def test_filter_movies_invalid_price_range(client, seed_database):
    min_price = 20.0
    max_price = 10.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?min_price={min_price}&max_price={max_price}"
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "min_price cannot be greater than max_price" in str(response_data["detail"])


@pytest.mark.asyncio
async def test_filter_movies_by_single_genre(client, db_session, seed_database):
    stmt = select(GenreModel).limit(1)
    result = await db_session.execute(stmt)
    genre = result.scalars().first()
    assert genre is not None

    genre_id = genre.id

    response = await client.get(f"{URL_PREFIX}/movies/?genre_ids={genre_id}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    movie_ids = [m["id"] for m in response_data["items"]]
    for movie_id in movie_ids:
        stmt_check = (
            select(MovieModel)
            .where(MovieModel.id == movie_id)
            .options(joinedload(MovieModel.genres))
        )
        result_check = await db_session.execute(stmt_check)
        movie = result_check.scalars().first()
        movie_genre_ids = [g.id for g in movie.genres]
        assert genre_id in movie_genre_ids, f"Movie {movie_id} doesn't have genre {genre_id}"


@pytest.mark.asyncio
async def test_filter_movies_by_multiple_genres(client, db_session, seed_database):
    stmt = select(GenreModel).limit(2)
    result = await db_session.execute(stmt)
    genres = result.scalars().all()
    assert len(genres) >= 2

    genre_ids = [genres[0].id, genres[1].id]
    genre_ids_str = ",".join(map(str, genre_ids))

    response = await client.get(f"{URL_PREFIX}/movies/?genre_ids={genre_ids_str}")
    assert response.status_code == 200

    response_data = response.json()

    movie_ids = [m["id"] for m in response_data["items"]]
    for movie_id in movie_ids:
        stmt_check = (
            select(MovieModel)
            .where(MovieModel.id == movie_id)
            .options(joinedload(MovieModel.genres))
        )
        result_check = await db_session.execute(stmt_check)
        movie = result_check.scalars().first()
        movie_genre_ids = [g.id for g in movie.genres]
        for genre_id in genre_ids:
            assert genre_id in movie_genre_ids, f"Movie {movie_id} missing genre {genre_id}"


@pytest.mark.asyncio
async def test_filter_movies_by_invalid_genre_ids(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/?genre_ids=abc,def")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_movies_by_certification(client, db_session, seed_database):
    stmt = (
        select(CertificationModel)
        .join(MovieModel)
        .group_by(CertificationModel.id)
        .limit(1)
    )
    result = await db_session.execute(stmt)
    certification = result.scalars().first()

    if not certification:
        pytest.skip("No certifications with movies found")

    cert_id = certification.id
    cert_name = certification.name

    response = await client.get(f"{URL_PREFIX}/movies/?certification_id={cert_id}")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["items"]) > 0

    for movie in response_data["items"]:
        assert movie["certification"] == cert_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort_by,sort_order",
    [
        ("price", "asc"),
        ("price", "desc"),
        ("year", "asc"),
        ("year", "desc"),
        ("imdb", "asc"),
        ("imdb", "desc"),
        ("votes", "asc"),
        ("votes", "desc"),
        ("name", "asc"),
        ("name", "desc"),
    ],
)
async def test_sort_movies(client, db_session, seed_database, sort_by, sort_order):
    response = await client.get(
        f"{URL_PREFIX}/movies/?sort_by={sort_by}&sort_order={sort_order}&per_page=20"
    )
    assert response.status_code == 200

    response_data = response.json()
    movies = response_data["items"]
    assert len(movies) > 1

    if sort_by == "price":
        values = [float(m["price"]) for m in movies]
    else:
        values = [m[sort_by] for m in movies]

    if sort_order == "asc":
        assert values == sorted(values), f"Movies not sorted ascending by {sort_by}"
    else:
        assert values == sorted(values, reverse=True), f"Movies not sorted descending by {sort_by}"


@pytest.mark.asyncio
async def test_combined_filters(client, db_session, seed_database):
    year_from = 2010
    year_to = 2020
    min_imdb = 6.5
    max_price = 15.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?"
        f"year_from={year_from}&year_to={year_to}&"
        f"min_imdb={min_imdb}&max_price={max_price}&"
        f"sort_by=imdb&sort_order=desc"
    )
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        assert year_from <= movie["year"] <= year_to
        assert movie["imdb"] >= min_imdb
        assert float(movie["price"]) <= max_price


@pytest.mark.asyncio
async def test_combined_filters_with_genre(client, db_session, seed_database):
    stmt = select(GenreModel).limit(1)
    result = await db_session.execute(stmt)
    genre = result.scalars().first()
    assert genre is not None

    min_imdb = 7.0
    max_price = 20.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?"
        f"min_imdb={min_imdb}&max_price={max_price}&"
        f"genre_ids={genre.id}"
    )
    assert response.status_code == 200

    response_data = response.json()

    for movie in response_data["items"]:
        assert movie["imdb"] >= min_imdb
        assert float(movie["price"]) <= max_price

        stmt_check = (
            select(MovieModel)
            .where(MovieModel.id == movie["id"])
            .options(joinedload(MovieModel.genres))
        )
        result_check = await db_session.execute(stmt_check)
        movie_obj = result_check.scalars().first()
        movie_genre_ids = [g.id for g in movie_obj.genres]
        assert genre.id in movie_genre_ids


@pytest.mark.asyncio
async def test_pagination_with_filters(client, db_session, seed_database):
    min_imdb = 6.0
    per_page = 5

    response_page1 = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb={min_imdb}&page=1&per_page={per_page}"
    )
    assert response_page1.status_code == 200
    data_page1 = response_page1.json()

    response_page2 = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb={min_imdb}&page=2&per_page={per_page}"
    )
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()

    assert data_page1["page"] == 1
    assert data_page2["page"] == 2
    assert data_page1["size"] == per_page
    assert data_page2["size"] == per_page

    if data_page1.get("next_page"):
        assert f"min_imdb={min_imdb}" in data_page1["next_page"]
    if data_page2.get("prev_page"):
        assert f"min_imdb={min_imdb}" in data_page2["prev_page"]

    movies_page1_ids = [m["id"] for m in data_page1["items"]]
    movies_page2_ids = [m["id"] for m in data_page2["items"]]
    assert len(set(movies_page1_ids) & set(movies_page2_ids)) == 0


@pytest.mark.asyncio
async def test_filter_with_no_results(client, seed_database):
    response = await client.get(
        f"{URL_PREFIX}/movies/?year_from=2050&year_to=2100"
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["items"]) == 0
    assert response_data["total_items"] == 0


@pytest.mark.asyncio
async def test_filter_extreme_values(client, seed_database):
    response = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb=9.9&max_price=0.01"
    )
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filter_param,invalid_value,expected_error",
    [
        ("min_imdb", 11.0, "less than or equal to 10"),
        ("max_imdb", -1.0, "greater than or equal to 0"),
        ("min_price", -5.0, "greater than or equal to 0"),
        ("year_from", 1800, "greater than or equal to 1900"),
        ("year_to", 2200, "less than or equal to 2100"),
    ],
)
async def test_filter_validation_errors(
    client,
    seed_database,
    filter_param,
    invalid_value,
    expected_error,
):
    response = await client.get(
        f"{URL_PREFIX}/movies/?{filter_param}={invalid_value}"
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data
    error_messages = str(response_data["detail"])
    assert expected_error in error_messages


@pytest.mark.asyncio
async def test_filter_results_match_database(client, db_session, seed_database):
    min_imdb = 7.0
    max_price = 15.0

    response = await client.get(
        f"{URL_PREFIX}/movies/?min_imdb={min_imdb}&max_price={max_price}&per_page=50"
    )
    assert response.status_code == 200
    api_movies = response.json()["items"]
    api_movie_ids = sorted([m["id"] for m in api_movies])

    stmt = (
        select(MovieModel)
        .where(MovieModel.imdb >= min_imdb)
        .where(MovieModel.price <= max_price)
        .order_by(MovieModel.imdb.desc())
        .limit(50)
    )
    result = await db_session.execute(stmt)
    db_movies = result.scalars().all()
    db_movie_ids = sorted([m.id for m in db_movies])

    assert api_movie_ids == db_movie_ids
