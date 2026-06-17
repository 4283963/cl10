from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class PipeNode(db.Model):
    __tablename__ = 'pipe_nodes'

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    node_type = db.Column(db.String(20), nullable=False, default='junction')
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    depth = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    gas_readings = db.relationship('GasReading', backref='node', lazy='dynamic',
                                  foreign_keys='GasReading.node_id')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'node_type': self.node_type,
            'x': self.x,
            'y': self.y,
            'depth': self.depth
        }


class PipeConnection(db.Model):
    __tablename__ = 'pipe_connections'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    from_node_id = db.Column(db.String(50), db.ForeignKey('pipe_nodes.id'), nullable=False)
    to_node_id = db.Column(db.String(50), db.ForeignKey('pipe_nodes.id'), nullable=False)
    distance = db.Column(db.Float, nullable=False, default=10.0)
    pipe_diameter = db.Column(db.Float, default=0.5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    from_node = db.relationship('PipeNode', foreign_keys=[from_node_id])
    to_node = db.relationship('PipeNode', foreign_keys=[to_node_id])

    def to_dict(self):
        return {
            'id': self.id,
            'from_node_id': self.from_node_id,
            'to_node_id': self.to_node_id,
            'distance': self.distance,
            'pipe_diameter': self.pipe_diameter
        }


class GasReading(db.Model):
    __tablename__ = 'gas_readings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    node_id = db.Column(db.String(50), db.ForeignKey('pipe_nodes.id'), nullable=False, index=True)
    h2s_concentration = db.Column(db.Float, nullable=False, default=0.0)
    ch4_concentration = db.Column(db.Float, nullable=False, default=0.0)
    temperature = db.Column(db.Float, default=25.0)
    humidity = db.Column(db.Float, default=60.0)
    robot_id = db.Column(db.String(50))
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'node_id': self.node_id,
            'h2s_concentration': self.h2s_concentration,
            'ch4_concentration': self.ch4_concentration,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'robot_id': self.robot_id,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }
