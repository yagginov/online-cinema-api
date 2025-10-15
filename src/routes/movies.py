import math
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import AnyUrl

from filters.movie_filters import MovieSearchParams
from repositories.movies import MovieRepository, get_movie_repository
from schemas.errors import NotFoundErrorResponse
from schemas.movies import (
    MovieCreateRequestSchema,
    MovieDetailResponseSchema,
    MovieListItemSchema,
    MoviePaginatedResponseSchema,
    MovieUpdateRequestSchema,
)

router = APIRouter()


@router.get(
    "/movies/",
    response_model=MoviePaginatedResponseSchema,
    summary="Get paginated list of movies",
    description="Retrieve a list of movies with pagination support.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Movies not found.",
            "model": NotFoundErrorResponse,
            "content": {
                "application/json": {
                    "example": NotFoundErrorResponse(detail="Movies not found."),
                },
            },
        },
    },
)
async def get_movies(
    request: Request,
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    # TODO make filtering
) -> MoviePaginatedResponseSchema:
    movies = await movie_repo.get_objects_or_404(
        offset=(page - 1) * size,
        limit=size,
        ordering=["-id"],
        # TODO make filtering
    )

    total = await movie_repo.get_total(
        # TODO make filtering
    )
    total_pages = math.ceil(total / size)

    next_page = AnyUrl(str(request.url.replace_query_params(page=page + 1, size=size))) if page < total_pages else None
    prev_page = AnyUrl(str(request.url.replace_query_params(page=page - 1, size=size))) if page > 1 else None

    return MoviePaginatedResponseSchema(
        items=[MovieListItemSchema.model_validate(movie) for movie in movies],
        page=page,
        size=size,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )


@router.get(
    "/movies/search/",
    response_model=MoviePaginatedResponseSchema,
    summary="Search movies",
    description="Search movies by title, description, star names, or director names.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "No search parameters provided.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "At least one search parameter must be provided (title, "
                            "description, star_names, or director_names)"
                        )
                    }
                },
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "No movies found matching the search criteria.",
            "model": NotFoundErrorResponse,
            "content": {
                "application/json": {
                    "example": NotFoundErrorResponse(detail="No movies found matching the search criteria."),
                },
            },
        },
    },
)
async def search_movies(
    request: Request,
    search_params: Annotated[MovieSearchParams, Depends()],
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
) -> MoviePaginatedResponseSchema:
    if not any(
        [
            search_params.title,
            search_params.description,
            search_params.star_names,
            search_params.director_names,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search parameter must be provided "
            "(title, description, star_names, or director_names)",
        )

    movies, total = await movie_repo.search_movies(
        search_params=search_params,
        load_relationships=True,
    )

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies found matching the search criteria.",
        )
    total_pages = math.ceil(total / search_params.per_page)

    next_page = (
        AnyUrl(str(request.url.replace_query_params(page=search_params.page + 1)))
        if search_params.page < total_pages
        else None
    )
    prev_page = (
        AnyUrl(str(request.url.replace_query_params(page=search_params.page - 1))) if search_params.page > 1 else None
    )

    return MoviePaginatedResponseSchema(
        items=[MovieListItemSchema.model_validate(movie) for movie in movies],
        page=search_params.page,
        size=search_params.per_page,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailResponseSchema,
    summary="Get movie by ID",
    description="Retrieve detailed information about a movie by its ID.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie not found.",
            "model": NotFoundErrorResponse,
            "content": {
                "application/json": {
                    "example": NotFoundErrorResponse(detail="Movie with the given ID was not found."),
                },
            },
        },
    },
)
async def get_movie_by_id(
    movie_id: int,
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
) -> MovieDetailResponseSchema:
    movie = await movie_repo.get_object_or_404(id=movie_id)
    return MovieDetailResponseSchema.model_validate(movie)


@router.post(
    "/movies/",
    status_code=status.HTTP_201_CREATED,
    response_model=MovieDetailResponseSchema,
    summary="Create a new movie",
    description="Create a new movie with its certification, genres, stars, and directors. "
    "All related entities will be automatically created if they do not exist.",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Movie successfully created.",
            "model": MovieDetailResponseSchema,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Movie with the same name, year, and time already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with name: 'Inception', " "year: '2010' and time: '148' already exist."
                    }
                },
            },
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Missing required related entities such as certification, genres, stars, or directors.",
        },
    },
)
async def create_movie(
    data: MovieCreateRequestSchema,
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
) -> MovieDetailResponseSchema:
    if await movie_repo.is_exist(name=data.name, year=data.year, time=data.time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Movie with name: '{data.name}', " f"year: '{data.year}' and time: '{data.time}' already exist."),
        )
    movie = await movie_repo.create_object(data)
    movie = await movie_repo.get_object_or_404(id=movie.id)
    return MovieDetailResponseSchema.model_validate(movie)


@router.patch(
    "/movies/{movie_id}/",
    status_code=status.HTTP_200_OK,
    response_model=MovieDetailResponseSchema,
    summary="Update an existing movie",
    description="Update fields of an existing movie by ID. "
    "Supports updating related entities (certification, genres, stars, directors). "
    "Only provided fields will be updated.",
    responses={
        status.HTTP_200_OK: {
            "description": "Movie successfully updated.",
            "model": MovieDetailResponseSchema,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with id=1 not found"},
                },
            },
        },
        status.HTTP_409_CONFLICT: {
            "description": "Another movie with the same name, year, and time already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with name: 'Inception', " "year: '2010' and time: '148' already exist."
                    }
                },
            },
        },
    },
)
async def update_movie(
    movie_id: int,
    data: MovieUpdateRequestSchema,
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
) -> MovieDetailResponseSchema:
    if await movie_repo.is_exist(name=data.name, year=data.year, time=data.time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Movie with name: '{data.name}', " f"year: '{data.year}' and time: '{data.time}' already exist."),
        )
    movie = await movie_repo.update_object(data, id=movie_id)
    return MovieDetailResponseSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete movie by ID",
    description="Delete a movie by its ID. Returns 204 if the deletion was successful.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Movie successfully deleted.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "The movie could not be deleted.",
            "content": {
                "application/json": {
                    "example": {"detail": "The movie was not deleted."},
                },
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with id=1 not found."},
                },
            },
        },
    },
)
async def delete_movie_by_id(
    movie_id: int,
    movie_repo: Annotated[MovieRepository, Depends(get_movie_repository)],
) -> None:
    if not await movie_repo.is_exist(id=movie_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    deleted = await movie_repo.delete_object(id=movie_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The movie was not deleted.",
        )
    return None
