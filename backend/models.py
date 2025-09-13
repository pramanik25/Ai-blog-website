# backend/models.py
from flask_sqlalchemy import SQLAlchemy
import datetime
from sqlalchemy import func

db = SQLAlchemy()

article_categories = db.Table('article_categories',
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)

    def to_dict(self):
        return {'name': self.name, 'slug': self.slug}


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), nullable=False, index=True) # Slugs may not be unique across languages
    lang = db.Column(db.String(10), nullable=False, default='en') # Language code (e.g., 'en', 'es', 'hi')
    title = db.Column(db.String(500), nullable=False)
    meta_description = db.Column(db.String(1000), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    is_breaking_news = db.Column(db.Boolean, default=False, nullable=False)
    author_name = db.Column(db.String(255), nullable=True)
    author_bio = db.Column(db.Text, nullable=True)
    categories = db.relationship('Category', secondary=article_categories, lazy='subquery',
        backref=db.backref('articles', lazy=True))

    # Link translations together
    original_article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=True)
    translations = db.relationship('Article', backref=db.backref('original_article', remote_side=[id]), lazy=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'lang': self.lang,
            'title': self.title,
            'meta_description': self.meta_description,
            'content': self.content,
            'image_url': self.image_url,
            'is_published': self.is_published,
            'is_breaking_news': self.is_breaking_news,
            'authorName': self.author_name,
            'authorBio': self.author_bio,
            'translations': [{'lang': t.lang, 'slug': t.slug} for t in self.translations],
            'categories': [category.to_dict() for category in self.categories] if self.categories else [],
            'createdAt': self.created_at.isoformat() if self.created_at else None, 
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None, 
        }

    def to_admin_dict(self):
        # This is a lightweight version for the admin list
        return {
            'id': self.id,
            'title': self.title,
            'is_published': self.is_published,
            'is_breaking_news': self.is_breaking_news,
            'lang': self.lang,
        }