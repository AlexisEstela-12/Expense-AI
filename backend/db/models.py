from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey

from .base import Base


class Movement(Base):
    __tablename__ = 'movements'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    kind = Column(String(24), nullable=False)
    currency = Column(String(3), nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    category = Column(String(80), nullable=False)
    description = Column(String(255), default='')
    exchange_id = Column(Integer, ForeignKey('exchanges.id'), nullable=True)
class Exchange(Base):
    __tablename__ = 'exchanges'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    from_currency = Column(String(3), nullable=False)
    amount_out = Column(Numeric(16, 2), nullable=False)
    amount_in = Column(Numeric(16, 2), nullable=False)
    rate = Column(Numeric(16, 6), nullable=False)
class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False)
    category = Column(String(80), nullable=False)
    currency = Column(String(3), nullable=False)
    limit_amount = Column(Numeric(16, 2), nullable=False)
class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    kind = Column(String(24), nullable=False)

class Reimbursement(Base):
    __tablename__ = 'reimbursements'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    currency = Column(String(3), nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    category = Column(String(80), nullable=False)
    description = Column(String(255), default='')
    status = Column(String(20), nullable=False, default='pending')
    reimbursed_date = Column(Date, nullable=True)

    movement_id = Column(
        Integer,
        ForeignKey('movements.id'),
        nullable=False
    )

    reimbursement_movement_id = Column(
        Integer,
        ForeignKey('movements.id'),
        nullable=True
    )

class RecurringPayment(Base):
    __tablename__ = 'recurring_payments'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(80), nullable=False)
    currency = Column(String(3), nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
    frequency = Column(String(20), nullable=False)
    next_payment_date = Column(Date, nullable=False)
    active = Column(Integer, nullable=False, default=1)

class SavingsGoal(Base):
    __tablename__ = 'savings_goals'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    currency = Column(String(3), nullable=False)
    target_amount = Column(Numeric(16, 2), nullable=False)
    target_date = Column(Date, nullable=True)
    active = Column(Integer, nullable=False, default=1)


class SavingsContribution(Base):
    __tablename__ = 'savings_contributions'

    id = Column(Integer, primary_key=True)
    goal_id = Column(
        Integer,
        ForeignKey('savings_goals.id'),
        nullable=False
    )
    date = Column(Date, nullable=False)
    amount = Column(Numeric(16, 2), nullable=False)
