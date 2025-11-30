"""
Character management module for D&D AI Dungeon Master.
Handles importing characters from D&D Beyond and storing them in PostgreSQL.
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get a database connection using DATABASE_URL."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)


def generate_character_id() -> str:
    """Generate a unique character ID."""
    timestamp = int(datetime.now().timestamp())
    return f"char_{timestamp}_{uuid.uuid4().hex[:8]}"


async def fetch_dndbeyond_character(character_id: str) -> dict:
    """
    Fetch character data from D&D Beyond API.
    
    Args:
        character_id: The D&D Beyond character ID (numeric string)
        
    Returns:
        The full character JSON data from D&D Beyond
        
    Raises:
        ValueError: If character ID is invalid
        httpx.HTTPStatusError: If the API request fails
    """
    numeric_id = character_id.strip()
    if not numeric_id.isdigit():
        raise ValueError(f"Invalid D&D Beyond character ID: {character_id}")
    
    url = f"https://character-service.dndbeyond.com/character/v5/character/{numeric_id}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


def extract_display_info(character_json: dict) -> dict:
    """
    Extract display information from D&D Beyond character JSON.
    
    Args:
        character_json: The full D&D Beyond character data
        
    Returns:
        Dictionary with extracted display values
    """
    data = character_json.get("data", character_json)
    
    name = data.get("name", "Unknown")
    
    race_info = data.get("race", {})
    race_name = race_info.get("fullName") or race_info.get("baseName", "Unknown")
    
    classes = data.get("classes", [])
    if classes:
        primary_class = classes[0]
        class_name = primary_class.get("definition", {}).get("name", "Unknown")
        level = primary_class.get("level", 1)
        total_level = sum(c.get("level", 0) for c in classes)
    else:
        class_name = "Unknown"
        level = 1
        total_level = 1
    
    base_hp = data.get("baseHitPoints") or 0
    removed_hp = data.get("removedHitPoints") or 0
    temp_hp = data.get("temporaryHitPoints") or 0
    bonus_hp = data.get("bonusHitPoints") or 0
    
    constitution_modifier = 0
    stats = data.get("stats", [])
    modifiers = data.get("modifiers", {})
    for stat in stats:
        if stat.get("id") == 3:
            base_con = stat.get("value") or 10
            constitution_modifier = (base_con - 10) // 2
            break
    
    max_hp = base_hp + bonus_hp + (constitution_modifier * total_level)
    current_hp = max_hp - removed_hp + temp_hp
    
    return {
        "name": name,
        "race": race_name,
        "class": class_name,
        "level": total_level,
        "currentHp": current_hp,
        "maxHp": max_hp
    }


async def import_character_from_dndbeyond(
    dndbeyond_id: str,
    campaign_id: Optional[str] = None
) -> dict:
    """
    Import a character from D&D Beyond and store in database.
    
    Args:
        dndbeyond_id: The D&D Beyond character ID
        campaign_id: Optional campaign to associate the character with
        
    Returns:
        The imported character record with display info
    """
    character_json = await fetch_dndbeyond_character(dndbeyond_id)
    
    char_id = generate_character_id()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO characters (id, dndbeyond_id, campaign_id, character_json)
                VALUES (%s, %s, %s, %s)
                RETURNING id, dndbeyond_id, campaign_id, created_at
                """,
                (char_id, dndbeyond_id, campaign_id, json.dumps(character_json))
            )
            result = cur.fetchone()
            conn.commit()
    finally:
        conn.close()
    
    if not result:
        raise RuntimeError("Failed to insert character into database")
    
    mirror_path = Path("mirror/characters") / char_id
    mirror_path.mkdir(parents=True, exist_ok=True)
    (mirror_path / "memories.txt").write_text("")
    
    display_info = extract_display_info(character_json)
    
    return {
        "id": result[0],
        "dndbeyond_id": result[1],
        "campaign_id": result[2],
        "created_at": result[3].isoformat() if result[3] else None,
        "source": "dndbeyond",
        **display_info
    }


async def get_character(character_id: str) -> Optional[dict]:
    """
    Get a character by ID.
    
    Args:
        character_id: The character's internal ID
        
    Returns:
        The character record with display info, or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, dndbeyond_id, campaign_id, character_json, created_at
                FROM characters
                WHERE id = %s
                """,
                (character_id,)
            )
            row = cur.fetchone()
    finally:
        conn.close()
    
    if not row:
        return None
    
    character_json = row["character_json"]
    if isinstance(character_json, str):
        character_json = json.loads(character_json)
    
    display_info = extract_display_info(character_json)
    
    return {
        "id": row["id"],
        "dndbeyond_id": row["dndbeyond_id"],
        "campaign_id": row["campaign_id"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "source": "dndbeyond" if row["dndbeyond_id"] else "manual",
        "character_json": character_json,
        **display_info
    }


async def get_character_json(character_id: str) -> Optional[dict]:
    """
    Get the full character JSON data.
    
    Args:
        character_id: The character's internal ID
        
    Returns:
        The full character JSON, or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT character_json FROM characters WHERE id = %s",
                (character_id,)
            )
            row = cur.fetchone()
    finally:
        conn.close()
    
    if not row:
        return None
    
    character_json = row[0]
    if isinstance(character_json, str):
        character_json = json.loads(character_json)
    
    return character_json


async def list_characters(campaign_id: Optional[str] = None) -> list[dict]:
    """
    List all characters, optionally filtered by campaign.
    
    Args:
        campaign_id: Optional campaign ID to filter by
        
    Returns:
        List of character records with display info
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if campaign_id:
                cur.execute(
                    """
                    SELECT id, dndbeyond_id, campaign_id, character_json, created_at
                    FROM characters
                    WHERE campaign_id = %s OR campaign_id IS NULL
                    ORDER BY created_at DESC
                    """,
                    (campaign_id,)
                )
            else:
                cur.execute(
                    """
                    SELECT id, dndbeyond_id, campaign_id, character_json, created_at
                    FROM characters
                    ORDER BY created_at DESC
                    """
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    
    characters = []
    for row in rows:
        character_json = row["character_json"]
        if isinstance(character_json, str):
            character_json = json.loads(character_json)
        
        display_info = extract_display_info(character_json)
        
        characters.append({
            "id": row["id"],
            "dndbeyond_id": row["dndbeyond_id"],
            "campaign_id": row["campaign_id"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "source": "dndbeyond" if row["dndbeyond_id"] else "manual",
            **display_info
        })
    
    return characters


async def delete_character(character_id: str) -> bool:
    """
    Delete a character by ID.
    
    Args:
        character_id: The character's internal ID
        
    Returns:
        True if deleted, False if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM characters WHERE id = %s RETURNING id",
                (character_id,)
            )
            deleted = cur.fetchone() is not None
            conn.commit()
    finally:
        conn.close()
    
    if deleted:
        mirror_path = Path("mirror/characters") / character_id
        if mirror_path.exists():
            import shutil
            shutil.rmtree(mirror_path)
    
    return deleted


async def update_character_campaign(character_id: str, campaign_id: Optional[str]) -> bool:
    """
    Update a character's campaign association.
    
    Args:
        character_id: The character's internal ID
        campaign_id: The new campaign ID (or None to unassociate)
        
    Returns:
        True if updated, False if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE characters 
                SET campaign_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
                """,
                (campaign_id, character_id)
            )
            updated = cur.fetchone() is not None
            conn.commit()
    finally:
        conn.close()
    
    return updated
