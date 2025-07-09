import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # Разделяем "data:image/png;base64,iVBORw0KGgoAAAANS..."
            # на формат и сам base64-код
            format, imgstr = data.split(';base64,')
            # Получаем расширение файла, например, png или jpeg
            ext = format.split('/')[-1]
            # Генерируем уникальное имя файла
            name = f"{uuid.uuid4()}.{ext}"
            # Декодируем base64 и создаем ContentFile с уникальным именем
            data = ContentFile(base64.b64decode(imgstr), name=name)
        return super().to_internal_value(data)
