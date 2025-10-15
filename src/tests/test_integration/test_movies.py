import random

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from database.models import (
    CertificationModel,
    GenreModel,
    MovieModel,
    StarModel,
)

URL_PREFIX = "/api/v1/cinema"


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    response = await client.get(f"{URL_PREFIX}/movies/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/")
    assert response.status_code == 200

    response_data = response.json()

    assert isinstance(response_data.get("items"), list)
    assert response_data.get("page") == 1
    assert response_data.get("size") == 10
    assert response_data.get("total_pages", 0) > 0
    assert response_data.get("total_items", 0) > 0

    assert response_data.get("prev_page") is None
    if response_data.get("total_pages", 0) > 1:
        assert response_data.get("next_page") is not None


@pytest.mark.asyncio
async def test_get_movies_with_custom_parameters(client, seed_database):
    page = 2
    per_page = 10

    response = await client.get(f"{URL_PREFIX}/movies/?page={page}&size={per_page}")
    assert response.status_code == 200
    response_data = response.json()

    assert len(response_data["items"]) == per_page
    assert response_data["page"] == page
    assert response_data["size"] == per_page

    if page > 1:
        expected_prev = str(f"{URL_PREFIX}/movies/?page={page-1}&size={per_page}")
        assert response_data["prev_page"].endswith(f"/movies/?page={page-1}&size={per_page}")

    if page < response_data["total_pages"]:
        assert response_data["next_page"] is not None
    else:
        assert response_data["next_page"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page, per_page, expected_detail",
    [
        (0, 10, "Input should be greater than or equal to 1"),
        (1, 0, "Input should be greater than or equal to 1"),
        (0, 0, "Input should be greater than or equal to 1"),
    ],
)
async def test_invalid_page_and_size(client, page, per_page, expected_detail):
    response = await client.get(f"{URL_PREFIX}/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data
    assert any(expected_detail in error.get("msg", "") for error in response_data["detail"])


@pytest.mark.asyncio
async def test_page_exceeds_maximum(client, db_session, seed_database):
    per_page = 10
    count_stmt = select(func.count(MovieModel.id))
    result = await db_session.execute(count_stmt)
    total_movies = result.scalar_one()

    max_page = (total_movies + per_page - 1) // per_page
    response = await client.get(f"{URL_PREFIX}/movies/?page={max_page + 1}&size={per_page}")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_movies_sorted_by_default_imdb_desc(client, db_session, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/?page=1&per_page=10")
    assert response.status_code == 200
    response_data = response.json()

    if len(response_data["items"]) > 1:
        imdb_ratings = [movie["imdb"] for movie in response_data["items"]]
        assert imdb_ratings == sorted(imdb_ratings, reverse=True), \
            "Movies should be sorted by IMDb rating in descending order by default"


@pytest.mark.asyncio
async def test_movie_list_with_pagination(client, db_session, seed_database):
    page = 2
    per_page = 5
    offset = (page - 1) * per_page

    response = await client.get(f"{URL_PREFIX}/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200
    response_data = response.json()

    count_stmt = select(func.count(MovieModel.id))
    count_result = await db_session.execute(count_stmt)
    total_items = count_result.scalar_one()

    import math
    total_pages = math.ceil(total_items / per_page)

    assert response_data["total_items"] == total_items
    assert response_data["total_pages"] == total_pages

    stmt = select(MovieModel).order_by(MovieModel.imdb.desc()).offset(offset).limit(per_page)

    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["items"]]

    assert expected_movie_ids == returned_movie_ids

    if page > 1:
        assert response_data["prev_page"] is not None
    else:
        assert response_data["prev_page"] is None

    if page < total_pages:
        assert response_data["next_page"] is not None
    else:
        assert response_data["next_page"] is None


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, seed_database):
    response = await client.get(f"{URL_PREFIX}/movies/?page=1&per_page=10")
    assert response.status_code == 200
    response_data = response.json()

    assert "items" in response_data

    expected_fields = {
        "id",
        "uuid",
        "name",
        "year",
        "time",
        "imdb",
        "votes",
        "meta_score",
        "gross",
        "description",
        "price",
        "certification",
    }

    for movie in response_data["items"]:
        assert expected_fields.issubset(set(movie.keys()))


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    movie_id = 1
    response = await client.get(f"{URL_PREFIX}/movies/{movie_id}/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_movie_by_id_valid(client, db_session, seed_database):
    stmt_min = select(MovieModel.id).order_by(MovieModel.id.asc()).limit(1)
    result_min = await db_session.execute(stmt_min)
    min_id = result_min.scalars().first()

    stmt_max = select(MovieModel.id).order_by(MovieModel.id.desc()).limit(1)
    result_max = await db_session.execute(stmt_max)
    max_id = result_max.scalars().first()

    random_id = random.randint(min_id, max_id)

    stmt_movie = select(MovieModel).where(MovieModel.id == random_id)
    result_movie = await db_session.execute(stmt_movie)
    expected_movie = result_movie.scalars().first()
    assert expected_movie is not None

    response = await client.get(f"{URL_PREFIX}/movies/{random_id}/")
    assert response.status_code == 200
    response_data = response.json()

    assert response_data["id"] == expected_movie.id
    assert response_data["name"] == expected_movie.name


@pytest.mark.asyncio
async def test_get_movie_by_id_fields_match_database(client, db_session, seed_database):
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    random_movie = result.scalars().first()
    assert random_movie is not None

    response = await client.get(f"{URL_PREFIX}/movies/{random_movie.id}/")
    assert response.status_code == 200
    response_data = response.json()

    assert response_data["id"] == random_movie.id
    assert response_data["name"] == random_movie.name
    assert response_data["year"] == random_movie.year
    assert response_data["time"] == random_movie.time
    assert response_data["imdb"] == random_movie.imdb
    assert response_data["votes"] == random_movie.votes
    assert response_data["meta_score"] == random_movie.meta_score
    assert response_data["gross"] == random_movie.gross
    assert response_data["description"] == random_movie.description
    assert float(response_data["price"]) == float(random_movie.price)

    assert response_data["certification"] == {
        "id": random_movie.certification.id,
        "name": random_movie.certification.name,
    }

    actual_genres = sorted(response_data["genres"], key=lambda x: x["id"])
    expected_genres = sorted(
        [{"id": genre.id, "name": genre.name} for genre in random_movie.genres],
        key=lambda x: x["id"],
    )
    assert actual_genres == expected_genres

    actual_stars = sorted(response_data["stars"], key=lambda x: x["id"])
    expected_stars = sorted(
        [{"id": star.id, "name": star.name} for star in random_movie.stars],
        key=lambda x: x["id"],
    )
    assert actual_stars == expected_stars

    actual_directors = sorted(response_data["directors"], key=lambda x: x["id"])
    expected_directors = sorted(
        [{"id": d.id, "name": d.name} for d in random_movie.directors],
        key=lambda x: x["id"],
    )
    assert actual_directors == expected_directors


@pytest.mark.asyncio
async def test_create_movie_and_related_models(client, db_session):
    movie_data = {
        "name": "New Movie",
        "year": 2025,
        "time": 120,
        "imdb": 8.5,
        "votes": 1000,
        "meta_score": None,
        "gross": None,
        "description": "An amazing movie.",
        "price": 12.50,
        "certification": "PG-13",
        "genres": ["Action", "Adventure"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["Dir One"],
    }

    response = await client.post(f"{URL_PREFIX}/movies/", json=movie_data)
    assert response.status_code == 201

    response_data = response.json()
    assert response_data["name"] == movie_data["name"]

    for genre_name in movie_data["genres"]:
        stmt = select(GenreModel).where(GenreModel.name == genre_name)
        result = await db_session.execute(stmt)
        genre = result.scalars().first()
        assert genre is not None

    for star_name in movie_data["stars"]:
        stmt = select(StarModel).where(StarModel.name == star_name)
        result = await db_session.execute(stmt)
        star = result.scalars().first()
        assert star is not None

    stmt = select(CertificationModel).where(CertificationModel.name == movie_data["certification"])
    result = await db_session.execute(stmt)
    cert = result.scalars().first()
    assert cert is not None


@pytest.mark.asyncio
async def test_create_movie_duplicate_error(client, db_session, seed_database):
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    existing_movie = result.scalars().first()
    assert existing_movie is not None

    movie_data = {
        "name": existing_movie.name,
        "year": existing_movie.year,
        "time": existing_movie.time,
        "imdb": existing_movie.imdb,
        "votes": existing_movie.votes,
        "meta_score": existing_movie.meta_score,
        "gross": existing_movie.gross,
        "description": existing_movie.description,
        "price": float(existing_movie.price),
        "certification": getattr(existing_movie.certification, "name", None),
        "genres": [g.name for g in existing_movie.genres],
        "stars": [s.name for s in existing_movie.stars],
        "directors": [d.name for d in existing_movie.directors],
    }

    response = await client.post(f"{URL_PREFIX}/movies/", json=movie_data)
    assert response.status_code == 409
    response_data = response.json()
    assert "detail" in response_data


@pytest.mark.asyncio
async def test_delete_movie_success(client, db_session, seed_database):
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None

    movie_id = movie.id
    response = await client.delete(f"{URL_PREFIX}/movies/{movie_id}/")
    assert response.status_code == 204

    stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
    result_check = await db_session.execute(stmt_check)
    deleted_movie = result_check.scalars().first()
    assert deleted_movie is None


@pytest.mark.asyncio
async def test_delete_movie_not_found(client):
    non_existent_id = 99999
    response = await client.delete(f"{URL_PREFIX}/movies/{non_existent_id}/")
    assert response.status_code == 404
    response_data = response.json()
    assert response_data["detail"] == "Movie with the given ID was not found."


@pytest.mark.asyncio
async def test_update_movie_success(client, db_session, seed_database):
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None

    movie_id = movie.id
    update_data = {"name": "Updated Movie Name", "imdb": 9.5}

    response = await client.patch(f"{URL_PREFIX}/movies/{movie_id}/", json=update_data)
    assert response.status_code == 200

    response_data = response.json()
    assert response_data["name"] == update_data["name"]
    assert response_data["imdb"] == update_data["imdb"]


@pytest.mark.asyncio
async def test_update_movie_not_found(client):
    non_existent_id = 99999
    update_data = {"name": "Non-existent Movie", "imdb": 9.0}

    response = await client.patch(f"{URL_PREFIX}/movies/{non_existent_id}/", json=update_data)
    assert response.status_code == 404
    response_data = response.json()
    assert "detail" in response_data
