import asyncio
import math
import random
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pandas as pd
from faker import Faker
from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from config import get_settings
from database import get_db_contextmanager
from database.models import (
    CertificationModel,
    DirectorModel,
    DirectorsMoviesModel,
    GenreModel,
    MovieModel,
    MoviesGenresModel,
    StarModel,
    StarsMoviesModel,
)

CHUNK_SIZE = 1000

# Official MPA (Motion Picture Association) film ratings
MPA_RATINGS = [
    "G",
    "PG",
    "PG-13",
    "R",
    "NC-17",
]

# Add some international ratings for variety
ADDITIONAL_RATINGS = [
    "U",
    "12A",
    "15",
    "18",
    "TV-MA",
    "TV-14",
    "TV-PG",
]

ALL_CERTIFICATIONS = MPA_RATINGS + ADDITIONAL_RATINGS


class CSVDatabaseSeeder:
    """
    A class responsible for seeding the database from a CSV file using asynchronous SQLAlchemy.
    """

    def __init__(self, csv_file_path: str, db_session: AsyncSession) -> None:
        """
        Initialize the seeder with the path to the CSV file and an async database session.

        :param csv_file_path: The path to the CSV file containing movie data.
        :param db_session: An instance of AsyncSession for performing database operations.
        """
        self._csv_file_path = csv_file_path
        self._db_session = db_session
        self._faker = Faker()

    async def is_db_populated(self) -> bool:
        """
        Check if the MovieModel table has at least one record.

        :return: True if there's already at least one movie in the database, otherwise False.
        """
        result = await self._db_session.execute(select(MovieModel).limit(1))
        first_movie = result.scalars().first()
        return first_movie is not None

    def _preprocess_csv(self) -> pd.DataFrame:
        """
        Load the CSV, remove duplicates, convert relevant columns to strings, and clean up data.
        Saves the cleaned CSV back to the same path, then returns the Pandas DataFrame.

        :return: A Pandas DataFrame containing cleaned movie data.
        """
        data = pd.read_csv(self._csv_file_path)

        # Remove duplicates based on name and date
        data = data.drop_duplicates(subset=["names", "date_x"], keep="first")

        # Fill NaN values and convert to strings
        for col in ["crew", "genre", "status", "country", "orig_lang"]:
            data[col] = data[col].fillna("Unknown").astype(str)

        # Clean crew column - remove whitespace and deduplicate
        data["crew"] = (
            data["crew"]
            .str.replace(r"\s+", "", regex=True)
            .apply(lambda x: ",".join(sorted(set(x.split(",")))) if x != "Unknown" else x)
        )

        # Clean genre column
        data["genre"] = data["genre"].str.replace("\u00a0", "", regex=True)

        # Parse date and extract year
        data["date_x"] = pd.to_datetime(data["date_x"], format="%Y-%m-%d", errors="coerce")
        data["year"] = data["date_x"].dt.year.fillna(2000).astype(int)

        # Handle score - convert to IMDB scale (0-10)
        data["score"] = pd.to_numeric(data["score"], errors="coerce").fillna(50.0)
        data["imdb"] = (data["score"] / 10.0).round(1)

        # Fill missing overview
        data["overview"] = data["overview"].fillna("No description available.")

        print("Preprocessing CSV file...")
        data.to_csv(self._csv_file_path, index=False)
        print(f"CSV file saved to {self._csv_file_path}")
        return data

    async def _get_or_create_bulk(self, model, items: List[str], unique_field: str) -> Dict[str, object]:
        """
        For a given model and a list of item names/keys (e.g., a list of genres),
        retrieves any existing records in the database matching these items.
        If some items are not found, they are created in bulk. Returns a dictionary
        mapping the item string to the corresponding model instance.

        :param model: The SQLAlchemy model class (e.g., GenreModel).
        :param items: A list of string values to create or retrieve (e.g., ["Comedy", "Action"]).
        :param unique_field: The field name that should be unique (e.g., "name").
        :return: A dict mapping each item to its model instance.
        """
        existing_dict: Dict[str, object] = {}

        if items:
            for i in range(0, len(items), CHUNK_SIZE):
                chunk = items[i : i + CHUNK_SIZE]
                result = await self._db_session.execute(select(model).where(getattr(model, unique_field).in_(chunk)))
                existing_in_chunk = result.scalars().all()
                for obj in existing_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        new_items = [item for item in items if item not in existing_dict]
        new_records = [{unique_field: item} for item in new_items]

        if new_records:
            for i in range(0, len(new_records), CHUNK_SIZE):
                chunk = new_records[i : i + CHUNK_SIZE]  # type: ignore
                await self._db_session.execute(insert(model).values(chunk))
                await self._db_session.flush()

            for i in range(0, len(new_items), CHUNK_SIZE):
                chunk = new_items[i : i + CHUNK_SIZE]
                result_new = await self._db_session.execute(
                    select(model).where(getattr(model, unique_field).in_(chunk))
                )
                inserted_in_chunk = result_new.scalars().all()
                for obj in inserted_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        return existing_dict

    async def _bulk_insert(self, table, data_list: List[Dict[str, int]]) -> None:
        """
        Insert data_list into the given table in chunks, displaying progress via tqdm.

        :param table: The SQLAlchemy table or model to insert into.
        :param data_list: A list of dictionaries, where each dict represents a row to insert.
        """
        total_records = len(data_list)
        if total_records == 0:
            return

        num_chunks = math.ceil(total_records / CHUNK_SIZE)
        table_name = getattr(table, "__tablename__", str(table))

        for chunk_index in tqdm(range(num_chunks), desc=f"Inserting into {table_name}"):
            start = chunk_index * CHUNK_SIZE
            end = start + CHUNK_SIZE
            chunk = data_list[start:end]
            if chunk:
                await self._db_session.execute(insert(table).values(chunk))

        await self._db_session.flush()

    async def _prepare_reference_data(
        self, data: pd.DataFrame
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Gather unique values for certifications, genres, stars, and directors from the DataFrame.
        Then call _get_or_create_bulk for each to ensure they exist in the database.

        :param data: The preprocessed Pandas DataFrame containing movie info.
        :return: A tuple of four dictionaries:
                 (certification_map, genre_map, star_map, director_map).
        """
        certifications = ALL_CERTIFICATIONS

        genres = {
            genre.strip()
            for genres_ in data["genre"].dropna()
            for genre in genres_.split(",")
            if genre.strip() and genre.strip() != "Unknown"
        }

        crew_members = {
            member.strip()
            for crew in data["crew"].dropna()
            for member in crew.split(",")
            if member.strip() and member.strip() != "Unknown"
        }

        crew_list = sorted(list(crew_members))
        split_point = int(len(crew_list) * 0.7)
        stars = crew_list[:split_point] if crew_list else []
        directors = crew_list[split_point:] if crew_list else []

        if not directors and stars:
            directors = stars[: max(1, len(stars) // 5)]

        certification_map = await self._get_or_create_bulk(CertificationModel, certifications, "name")
        genre_map = await self._get_or_create_bulk(GenreModel, list(genres), "name")
        star_map = await self._get_or_create_bulk(StarModel, stars, "name")
        director_map = await self._get_or_create_bulk(DirectorModel, directors, "name")

        return certification_map, genre_map, star_map, director_map

    def _prepare_movies_data(self, data: pd.DataFrame, certification_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build a list of dictionaries representing movie records to be inserted into MovieModel.

        :param data: The preprocessed DataFrame.
        :param certification_map: A mapping of certification names to CertificationModel instances.
        :return: A list of dictionaries, each representing a new movie record.
        """
        movies_data: List[Dict[str, Any]] = []

        for _, row in tqdm(data.iterrows(), total=data.shape[0], desc="Processing movies"):
            # Assign random but appropriate certification based on IMDB score
            imdb_score = float(row["imdb"])
            if imdb_score >= 7.5:
                # Higher rated movies tend to be PG-13 or R
                cert_name = random.choice(["PG-13", "R", "PG", "12A"])
            elif imdb_score >= 6.0:
                cert_name = random.choice(["PG-13", "PG", "R", "12A", "15"])
            else:
                # Lower rated movies more varied
                cert_name = random.choice(ALL_CERTIFICATIONS)

            certification = certification_map[cert_name]

            # Generate realistic movie duration based on genre
            genres = row["genre"].lower()
            if "documentary" in genres:
                time = random.randint(60, 120)
            elif "animation" in genres:
                time = random.randint(75, 110)
            elif "action" in genres or "adventure" in genres:
                time = random.randint(100, 160)
            elif "drama" in genres:
                time = random.randint(90, 180)
            else:
                time = random.randint(80, 140)

            # Generate realistic votes count based on IMDB score and year
            year = int(row["year"])
            base_votes = float(random.randint(5000, 100000))

            # More recent and higher-rated movies get more votes
            if year >= 2020:
                base_votes *= random.uniform(2, 5)
            elif year >= 2015:
                base_votes *= random.uniform(1.5, 3)

            if imdb_score >= 8.0:
                base_votes *= random.uniform(3, 10)
            elif imdb_score >= 7.0:
                base_votes *= random.uniform(1.5, 3)

            votes = int(base_votes)

            # Meta score is often correlated with IMDB but with variance
            if random.random() > 0.6:  # 40% of movies have meta_score
                meta_score = round(imdb_score + random.uniform(-1.5, 1.5), 2)
                meta_score = max(2.0, min(10.0, meta_score))  # Clamp between 2-10
            else:
                meta_score = None

            # Calculate gross based on revenue
            if pd.notna(row["revenue"]) and row["revenue"] > 0:
                # Domestic gross is typically 30-60% of worldwide revenue
                gross: float | None = round(float(row["revenue"]) * random.uniform(0.3, 0.6), 2)
            else:
                # Generate fake box office if no revenue data
                if imdb_score >= 7.0:
                    gross = random.uniform(50_000_000, 500_000_000)
                else:
                    gross = random.uniform(5_000_000, 100_000_000) if random.random() > 0.3 else None

            # Price based on movie year and rating
            if year >= 2022:
                price = Decimal(str(round(random.uniform(14.99, 19.99), 2)))
            elif year >= 2018:
                price = Decimal(str(round(random.uniform(9.99, 14.99), 2)))
            elif year >= 2010:
                price = Decimal(str(round(random.uniform(5.99, 9.99), 2)))
            else:
                price = Decimal(str(round(random.uniform(2.99, 7.99), 2)))

            movie = {
                "name": row["names"],
                "year": year,
                "time": time,
                "imdb": imdb_score,
                "votes": votes,
                "meta_score": meta_score,
                "gross": gross,
                "description": row["overview"],
                "price": price,
                "certification_id": certification.id,
            }
            movies_data.append(movie)

        return movies_data

    def _prepare_associations(
        self,
        data: pd.DataFrame,
        movie_ids: List[int],
        genre_map: Dict[str, Any],
        star_map: Dict[str, Any],
        director_map: Dict[str, Any],
    ) -> Tuple[List[Dict[str, int]], List[Dict[str, int]], List[Dict[str, int]]]:
        """
        Prepare three lists of dictionaries: movie-genre, movie-star, and movie-director
        associations for all movies in the DataFrame.

        :param data: The DataFrame containing movie info.
        :param movie_ids: The list of newly inserted movie IDs, in the same order as DataFrame rows.
        :param genre_map: A mapping of genre names to GenreModel instances.
        :param star_map: A mapping of star names to StarModel instances.
        :param director_map: A mapping of director names to DirectorModel instances.
        :return: A tuple of three lists:
                 (movie_genres_data, movie_stars_data, movie_directors_data),
                 each containing dictionaries for bulk insertion.
        """
        movie_genres_data: List[Dict[str, int]] = []
        movie_stars_data: List[Dict[str, int]] = []
        movie_directors_data: List[Dict[str, int]] = []

        # Get all director names for checking
        director_names = set(director_map.keys())

        for i, (_, row) in enumerate(tqdm(data.iterrows(), total=data.shape[0], desc="Processing associations")):
            movie_id = movie_ids[i]

            # Add genres
            for genre_name in row["genre"].split(","):
                genre_name = genre_name.strip()
                if genre_name and genre_name != "Unknown" and genre_name in genre_map:
                    genre = genre_map[genre_name]
                    movie_genres_data.append({"movie_id": movie_id, "genre_id": genre.id})

            # Process crew - split into stars and directors
            crew_members = [c.strip() for c in row["crew"].split(",") if c.strip() and c.strip() != "Unknown"]

            for crew_name in crew_members:
                # If person is in director_map, add as director
                if crew_name in director_names:
                    director = director_map[crew_name]
                    movie_directors_data.append({"movie_id": movie_id, "director_id": director.id})
                # Otherwise, if in star_map, add as star
                elif crew_name in star_map:
                    star = star_map[crew_name]
                    movie_stars_data.append({"movie_id": movie_id, "star_id": star.id})

        return movie_genres_data, movie_stars_data, movie_directors_data

    async def seed(self) -> None:
        """
        Main method to seed the database with movie data from the CSV.
        It pre-processes the CSV, prepares reference data (certifications, genres, stars, directors),
        inserts all movies, then inserts many-to-many relationships (genres, stars, directors).
        """
        try:
            if self._db_session.in_transaction():
                print("Rolling back existing transaction.")
                await self._db_session.rollback()

            data = self._preprocess_csv()

            certification_map, genre_map, star_map, director_map = await self._prepare_reference_data(data)

            movies_data = self._prepare_movies_data(data, certification_map)

            result = await self._db_session.execute(insert(MovieModel).returning(MovieModel.id), movies_data)
            movie_ids = list(result.scalars().all())

            movie_genres_data, movie_stars_data, movie_directors_data = self._prepare_associations(
                data, movie_ids, genre_map, star_map, director_map
            )

            await self._bulk_insert(MoviesGenresModel, movie_genres_data)
            await self._bulk_insert(StarsMoviesModel, movie_stars_data)
            await self._bulk_insert(DirectorsMoviesModel, movie_directors_data)

            await self._db_session.commit()
            print("Seeding completed.")

        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            await self._db_session.rollback()
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            await self._db_session.rollback()
            raise


async def main() -> None:
    """
    The main async entry point for running the database seeder.
    Checks if the database is already populated, and if not, performs the seeding process.
    """
    settings = get_settings()
    async with get_db_contextmanager() as db_session:
        seeder = CSVDatabaseSeeder(settings.PATH_TO_MOVIES_CSV, db_session)

        if not await seeder.is_db_populated():
            try:
                await seeder.seed()
                print("Database seeding completed successfully.")
            except Exception as e:
                print(f"Failed to seed the database: {e}")
        else:
            print("Database is already populated. Skipping seeding.")


if __name__ == "__main__":
    asyncio.run(main())
