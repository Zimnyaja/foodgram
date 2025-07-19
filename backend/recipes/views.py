from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from .models import Recipe
from .utils.shortener import decode_code


def redirect_short_link(request, code):
    recipe_id = decode_code(code)
    try:
        Recipe.objects.get(id=recipe_id)
    except Recipe.DoesNotExist:
        return redirect('/404')
    return HttpResponseRedirect(f'/recipes/{recipe_id}')
