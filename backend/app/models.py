from sqlalchemy import Column, String, Date, Numeric, BigInteger, SmallInteger, Boolean, DateTime, Integer, func
from .database import Base


class ListedStock(Base):
    __tablename__ = "listed_stocks"
    code         = Column(String(10), primary_key=True)
    company_name = Column(String(255))
    market_code  = Column(String(10))
    sector_code  = Column(String(10))
    updated_at   = Column(DateTime, default=func.now())


class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    code           = Column(String(10), primary_key=True)
    date           = Column(Date, primary_key=True)
    open           = Column(Numeric)
    high           = Column(Numeric)
    low            = Column(Numeric)
    close          = Column(Numeric)
    volume         = Column(BigInteger)
    turnover_value = Column(Numeric)
    adj_close      = Column(Numeric)
    adj_volume     = Column(BigInteger)
    adj_factor     = Column(Numeric)


class Prediction(Base):
    __tablename__ = "predictions"
    id             = Column(Integer, primary_key=True)
    code           = Column(String(10), nullable=False)
    date           = Column(Date, nullable=False)
    up_probability = Column(Numeric, nullable=False)
    signal         = Column(String(10), nullable=False)
    predicted_at   = Column(DateTime, default=func.now())
    actual_return  = Column(Numeric)
    is_correct     = Column(Boolean)
