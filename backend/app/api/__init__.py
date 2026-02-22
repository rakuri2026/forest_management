"""API routers"""
from .auth import router as auth_router
from .forests import router as forests_router
from .inventory import router as inventory_router
from .species import router as species_router
from .tree_models import router as tree_models_router
from . import biodiversity

__all__ = ["auth_router", "forests_router", "inventory_router", "species_router", "tree_models_router", "biodiversity"]
