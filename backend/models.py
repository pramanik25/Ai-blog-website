# backend/models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    meta_description = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        # This is for the full article view
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'meta_description': self.meta_description,
            'content': self.content,
            'image_url': self.image_url,
            'is_published': self.is_published,
        }

    def to_admin_dict(self):
        # This is a lightweight version for the admin list
        return {
            'id': self.id,
            'title': self.title,
            'is_published': self.is_published,
        }