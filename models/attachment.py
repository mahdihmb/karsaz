from sqlalchemy import Column, String, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from limoo_driver_provider import LIMOO_HOST
from . import Base


class Attachment(Base):
    __tablename__ = "attachments"

    hash = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    mime_type = Column(String)
    size = Column(BigInteger)

    task_id = Column(String, ForeignKey('tasks.id'))
    task = relationship('Task', back_populates='attachments')

    def link(self, view_mode=False):
        return (
            f'[{":sunrise_over_mountains: نمایش" if view_mode else ":arrow_down: دانلود"}](https://{LIMOO_HOST}/fileserver/api/v1/files'
            f'?hash={self.hash}&file_name={self.name}&mode={"view" if view_mode else "download"})'
        )

    def thumbnail(self, view_mode=False):
        return f'![{self.name}](/fileserver/api/v1/files/thumbnail?hash={self.hash}&mode=view =x25 "{self.name}")'

    def table_row(self):
        row = f"|{self.name}"
        if self.mime_type.startswith("image/"):
            row += f" {self.thumbnail()}"
        row += f"|{self.link()} {self.link(view_mode=True)}|\n"
        return row
