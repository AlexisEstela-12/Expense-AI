from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Category
    from ...schemas.categories import CategoryIn
else:
    from db.models import Category
    from schemas.categories import CategoryIn


def create_router(db):
    router = APIRouter()

    @router.get('/categories')
    def get_categories(session: Session = Depends(db)):
        items = session.scalars(
            select(Category).order_by(
                Category.kind.asc(),
                Category.name.asc()
            )
        ).all()

        return [
            {
                'id': category.id,
                'name': category.name,
                'kind': category.kind
            }
            for category in items
        ]

    @router.post('/categories', status_code=201)
    def create_category(payload: CategoryIn, session: Session = Depends(db)):
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail='La categoría no puede estar vacía.'
            )

        existing = session.scalars(
            select(Category).where(
                Category.kind == payload.kind,
                Category.name == name
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail='Esta categoría ya existe.'
            )

        category = Category(
            name=name,
            kind=payload.kind
        )

        session.add(category)
        session.commit()
        session.refresh(category)

        return {
            'id': category.id,
            'name': category.name,
            'kind': category.kind
        }

    return router
