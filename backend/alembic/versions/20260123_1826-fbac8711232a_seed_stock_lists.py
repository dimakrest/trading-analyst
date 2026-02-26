"""seed_stock_lists

Revision ID: fbac8711232a
Revises: 4e3891cf488d
Create Date: 2026-01-23 18:26:00.000000

Seeds predefined stock lists for common trading categories.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fbac8711232a'
down_revision: Union[str, Sequence[str], None] = '4e3891cf488d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Predefined stock lists (user_id=1 for shared/system lists)
SEED_LISTS = [
    {
        "name": "Risk On",
        "user_id": 1,
        "symbols": [
            "ACHR", "ASTS", "BBAI", "BITF", "BMNR", "BTQ", "CIFR", "EOSE",
            "GEV", "GLXY", "HUT", "IONQ", "IREN", "JOBY", "MARA", "MSTR",
            "NBIS", "NNE", "OKLO", "OPEN", "PONY", "QBTS", "QUBT", "RGTI",
            "RIOT", "RKLB", "SBET", "SMR", "SOUN", "WULF",
        ],
    },
    {
        "name": "Space",
        "user_id": 1,
        "symbols": [
            "ASTS", "LUNR", "RDW", "RKLB", "SATS", "RTX", "HEI",
            "LMT", "SPIR", "LHX", "NOC", "ARKX", "UFO",
            "AIR", "PL", "IRDM", "BA", "BKSY", "VSAT", "SIDU",
            "SPCE", "FLY",
        ],
    },
    {
        "name": "Finance",
        "user_id": 1,
        "symbols": ["XLF", "KRE", "MA", "V", "JPM", "BAC", "LC", "AXP", "BLK"],
    },
    {
        "name": "Robotics",
        "user_id": 1,
        "symbols": ["ARKQ", "PATH", "ROK", "CGNX", "ZBRA", "PEGA", "TER"],
    },
]


def upgrade() -> None:
    """Seed predefined stock lists."""
    for list_data in SEED_LISTS:
        symbols_array = "{" + ",".join(list_data["symbols"]) + "}"
        op.execute(
            f"""
            INSERT INTO stock_lists (user_id, name, symbols, created_at, updated_at)
            VALUES (
                {list_data['user_id']},
                '{list_data['name']}',
                '{symbols_array}',
                NOW(),
                NOW()
            )
            ON CONFLICT DO NOTHING
            """
        )


def downgrade() -> None:
    """Remove seeded stock lists."""
    for list_data in SEED_LISTS:
        op.execute(
            f"""
            DELETE FROM stock_lists
            WHERE user_id = {list_data['user_id']}
            AND name = '{list_data['name']}'
            """
        )
