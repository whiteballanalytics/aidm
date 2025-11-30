"""
PDF Character Sheet Parser for D&D Beyond exported character sheets.
Extracts form field data and converts to D&D Beyond-compatible JSON format.
"""

import re
import io
from typing import Optional
from pypdf import PdfReader


def extract_form_fields(pdf_content: bytes) -> dict:
    """
    Extract all form field values from a D&D Beyond PDF.
    
    Args:
        pdf_content: Raw PDF file bytes
        
    Returns:
        Dictionary mapping field names to values
    """
    reader = PdfReader(io.BytesIO(pdf_content))
    
    all_fields = {}
    
    for page in reader.pages:
        if '/Annots' in page:
            annots = page['/Annots']
            for annot_ref in annots:
                try:
                    annot = annot_ref.get_object()
                    name = annot.get('/T')
                    value = annot.get('/V')
                    if name:
                        all_fields[str(name)] = str(value) if value else ''
                except Exception:
                    pass
    
    return all_fields


def parse_class_level_from_fields(fields: dict) -> list[dict]:
    """
    Parse class and level information from form fields.
    
    Returns:
        List of class dictionaries with name and level
    """
    class_level = fields.get('CLASS  LEVEL', '') or fields.get('CLASS LEVEL', '')
    
    classes = []
    class_pattern = r'([A-Za-z]+)\s+(\d+)'
    matches = re.findall(class_pattern, class_level)
    
    for class_name, level in matches:
        classes.append({
            "definition": {"name": class_name.title()},
            "level": int(level)
        })
    
    return classes if classes else [{"definition": {"name": "Unknown"}, "level": 1}]


def parse_ability_scores_from_fields(fields: dict) -> dict:
    """
    Parse ability scores from form fields.
    
    Returns:
        Dictionary of ability scores
    """
    def safe_int(value: str, default: int = 10) -> int:
        try:
            return int(value.strip())
        except (ValueError, AttributeError):
            return default
    
    return {
        "strength": safe_int(fields.get('STR', '10')),
        "dexterity": safe_int(fields.get('DEX', '10')),
        "constitution": safe_int(fields.get('CON', '10')),
        "intelligence": safe_int(fields.get('INT', '10')),
        "wisdom": safe_int(fields.get('WIS', '10')),
        "charisma": safe_int(fields.get('CHA', '10'))
    }


def parse_hp_from_fields(fields: dict) -> tuple[int, int]:
    """
    Parse HP values from form fields.
    
    Returns:
        Tuple of (max_hp, current_hp)
    """
    def safe_int(value: str, default: int = 10) -> int:
        try:
            clean = re.sub(r'[^\d]', '', str(value))
            return int(clean) if clean else default
        except (ValueError, AttributeError):
            return default
    
    max_hp = safe_int(fields.get('MaxHP', '10'))
    
    current_hp_str = fields.get('CurrentHP', '') or fields.get('Current HP', '')
    if current_hp_str and current_hp_str.strip() and current_hp_str.strip() != '--':
        current_hp = safe_int(current_hp_str)
    else:
        current_hp = max_hp
    
    temp_hp_str = fields.get('TempHP', '') or fields.get('Temp HP', '')
    temp_hp = 0
    if temp_hp_str and temp_hp_str.strip() and temp_hp_str.strip() not in ('--', '0'):
        temp_hp = safe_int(temp_hp_str, 0)
    
    return max_hp, current_hp + temp_hp


def parse_armor_class_from_fields(fields: dict) -> int:
    """Parse armor class from form fields."""
    ac_str = fields.get('AC', '10')
    try:
        return int(ac_str.strip())
    except (ValueError, AttributeError):
        return 10


def parse_speed_from_fields(fields: dict) -> int:
    """Parse walking speed from form fields."""
    speed_str = fields.get('Speed', '30 ft.')
    match = re.search(r'(\d+)', speed_str)
    if match:
        return int(match.group(1))
    return 30


def parse_proficiency_bonus_from_fields(fields: dict) -> int:
    """Parse proficiency bonus from form fields."""
    prof_str = fields.get('ProfBonus', '+2')
    match = re.search(r'[+]?(\d+)', prof_str)
    if match:
        return int(match.group(1))
    return 2


def parse_proficiencies_from_fields(fields: dict) -> dict:
    """Parse proficiencies from form fields."""
    proficiencies = {
        "armor": [],
        "weapons": [],
        "tools": [],
        "skills": [],
        "languages": []
    }
    
    prof_text = fields.get('ProficienciesLang', '')
    
    armor_match = re.search(r'=== ARMOR ===\s*\n?([^=]+)', prof_text)
    if armor_match:
        armor_text = armor_match.group(1).strip()
        proficiencies["armor"] = [a.strip() for a in armor_text.split(',') if a.strip()]
    
    weapons_match = re.search(r'=== WEAPONS ===\s*\n?([^=]+)', prof_text)
    if weapons_match:
        weapons_text = weapons_match.group(1).strip()
        proficiencies["weapons"] = [w.strip() for w in weapons_text.split(',') if w.strip()]
    
    tools_match = re.search(r'=== TOOLS ===\s*\n?([^=]+)', prof_text)
    if tools_match:
        tools_text = tools_match.group(1).strip()
        proficiencies["tools"] = [t.strip() for t in tools_text.split(',') if t.strip()]
    
    lang_match = re.search(r'=== LANGUAGES ===\s*\n?([^=]+)', prof_text)
    if lang_match:
        lang_text = lang_match.group(1).strip()
        proficiencies["languages"] = [l.strip() for l in lang_text.split(',') if l.strip()]
    
    skill_fields = [
        ('Acrobatics', 'AcrobaticsProf'),
        ('Animal', 'AnimalProf'),
        ('Arcana', 'ArcanaProf'),
        ('Athletics', 'AthleticsProf'),
        ('Deception', 'DeceptionProf'),
        ('History', 'HistoryProf'),
        ('Insight', 'InsightProf'),
        ('Intimidation', 'IntimidationProf'),
        ('Investigation', 'InvestigationProf'),
        ('Medicine', 'MedicineProf'),
        ('Nature', 'NatureProf'),
        ('Perception', 'PerceptionProf'),
        ('Performance', 'PerformanceProf'),
        ('Persuasion', 'PersuasionProf'),
        ('Religion', 'ReligionProf'),
        ('SleightofHand', 'SleightofHandProf'),
        ('Stealth', 'StealthProf'),
        ('Survival', 'SurvivalProf')
    ]
    
    skill_names = {
        'Acrobatics': 'Acrobatics',
        'Animal': 'Animal Handling',
        'Arcana': 'Arcana',
        'Athletics': 'Athletics',
        'Deception': 'Deception',
        'History': 'History',
        'Insight': 'Insight',
        'Intimidation': 'Intimidation',
        'Investigation': 'Investigation',
        'Medicine': 'Medicine',
        'Nature': 'Nature',
        'Perception': 'Perception',
        'Performance': 'Performance',
        'Persuasion': 'Persuasion',
        'Religion': 'Religion',
        'SleightofHand': 'Sleight of Hand',
        'Stealth': 'Stealth',
        'Survival': 'Survival'
    }
    
    for skill_key, prof_key in skill_fields:
        if fields.get(prof_key, '').strip() == 'P':
            proficiencies["skills"].append(skill_names[skill_key])
    
    return proficiencies


def parse_weapons_from_fields(fields: dict) -> list[dict]:
    """Parse weapon attacks from form fields."""
    weapons = []
    
    for i in range(10):
        name = fields.get(f'Wpn Name{i}', '') or fields.get(f'WpnName{i}', '')
        attack_bonus = fields.get(f'Wpn{i} AtkBonus', '') or fields.get(f'Wpn{i}AtkBonus', '')
        damage = fields.get(f'Wpn{i} Damage', '') or fields.get(f'Wpn{i}Damage', '')
        
        if name and name.strip():
            weapon = {
                "name": name.strip()
            }
            
            bonus_match = re.search(r'[+]?(\d+)', attack_bonus)
            if bonus_match:
                weapon["attackBonus"] = int(bonus_match.group(1))
            
            if damage:
                weapon["damage"] = damage.strip()
            
            weapons.append(weapon)
    
    return weapons


def parse_equipment_from_fields(fields: dict) -> list[dict]:
    """Parse equipment list from form fields."""
    equipment = []
    
    for i in range(20):
        name = fields.get(f'Eq Name{i}', '')
        qty = fields.get(f'Eq Qty{i}', '1')
        weight = fields.get(f'Eq Weight{i}', '--')
        
        if name and name.strip():
            equipment.append({
                "name": name.strip(),
                "quantity": int(qty) if qty.isdigit() else 1,
                "weight": weight.strip() if weight else '--'
            })
    
    return equipment


def parse_spells_from_fields(fields: dict) -> list[dict]:
    """Parse known spells from form fields."""
    spells = []
    
    for i in range(30):
        name = fields.get(f'spellName{i}', '')
        level = fields.get(f'spellLevel{i}', '')
        school = fields.get(f'spellSchool{i}', '')
        casting_time = fields.get(f'spellCastingTime{i}', '')
        range_val = fields.get(f'spellRange{i}', '')
        duration = fields.get(f'spellDuration{i}', '')
        source = fields.get(f'spellSource{i}', '')
        
        if name and name.strip():
            spells.append({
                "name": name.strip(),
                "level": level.strip() if level else '0',
                "school": school.strip() if school else '',
                "castingTime": casting_time.strip() if casting_time else '',
                "range": range_val.strip() if range_val else '',
                "duration": duration.strip() if duration else '',
                "source": source.strip() if source else ''
            })
    
    return spells


def parse_senses_from_fields(fields: dict) -> str:
    """Parse senses from form fields."""
    return fields.get('AdditionalSenses', '') or fields.get('Senses', '')


def parse_defenses_from_fields(fields: dict) -> str:
    """Parse defenses/resistances from form fields."""
    return fields.get('Defenses', '')


def parse_hit_dice_from_fields(fields: dict) -> str:
    """Parse hit dice from form fields."""
    return fields.get('Total', '1d8')


def parse_save_modifiers_from_fields(fields: dict) -> str:
    """Parse saving throw modifiers from form fields."""
    return fields.get('SaveModifiers', '')


def parse_pdf_to_dndbeyond_json(pdf_content: bytes) -> dict:
    """
    Parse a D&D Beyond PDF character sheet and convert to D&D Beyond JSON format.
    
    Args:
        pdf_content: Raw PDF file bytes
        
    Returns:
        Dictionary in D&D Beyond API format
    """
    fields = extract_form_fields(pdf_content)
    
    if not fields:
        raise ValueError("Could not extract form fields from PDF. The PDF may be corrupted or in an unsupported format.")
    
    classes = parse_class_level_from_fields(fields)
    abilities = parse_ability_scores_from_fields(fields)
    max_hp, current_hp = parse_hp_from_fields(fields)
    proficiencies = parse_proficiencies_from_fields(fields)
    
    total_level = sum(c.get("level", 1) for c in classes)
    if total_level == 0:
        total_level = 1
    
    character_data = {
        "data": {
            "id": None,
            "name": fields.get('CharacterName', 'Unknown Character').strip(),
            "race": {
                "fullName": fields.get('RACE', 'Unknown').strip() or fields.get('Race', 'Unknown').strip(),
                "baseName": fields.get('RACE', 'Unknown').strip() or fields.get('Race', 'Unknown').strip()
            },
            "classes": classes,
            "stats": [
                {"id": 1, "name": "strength", "value": abilities["strength"]},
                {"id": 2, "name": "dexterity", "value": abilities["dexterity"]},
                {"id": 3, "name": "constitution", "value": abilities["constitution"]},
                {"id": 4, "name": "intelligence", "value": abilities["intelligence"]},
                {"id": 5, "name": "wisdom", "value": abilities["wisdom"]},
                {"id": 6, "name": "charisma", "value": abilities["charisma"]}
            ],
            "baseHitPoints": max_hp,
            "removedHitPoints": max(0, max_hp - current_hp),
            "temporaryHitPoints": 0,
            "bonusHitPoints": 0,
            "armorClass": parse_armor_class_from_fields(fields),
            "speed": parse_speed_from_fields(fields),
            "proficiencyBonus": parse_proficiency_bonus_from_fields(fields),
            "languages": proficiencies.get("languages", ["Common"]),
            "proficiencies": proficiencies,
            "weapons": parse_weapons_from_fields(fields),
            "equipment": parse_equipment_from_fields(fields),
            "spells": parse_spells_from_fields(fields),
            "hitDice": parse_hit_dice_from_fields(fields),
            "senses": parse_senses_from_fields(fields),
            "defenses": parse_defenses_from_fields(fields),
            "saveModifiers": parse_save_modifiers_from_fields(fields),
            "source": "pdf_import"
        },
        "success": True
    }
    
    return character_data


def parse_pdf_file(pdf_path: str) -> dict:
    """
    Parse a PDF file and return D&D Beyond-compatible JSON.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary in D&D Beyond API format
    """
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    
    return parse_pdf_to_dndbeyond_json(pdf_content)
