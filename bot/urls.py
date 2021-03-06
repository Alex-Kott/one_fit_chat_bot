from django.conf.urls import url
from django.conf import settings
from django.conf.urls.static import static

from . import views




urlpatterns = [
    url(r'^$', views.auth, name='auth'),
    # url(r'^auth/', views.auth, name='auth'),
    url(r'^deauth/', views.deauth, name='deauth'),
    url(r'^admin/', views.admin, name='admin'),
    url(r'^add-trainer-photo/', views.add_trainer_photo, name='add-trainer-photo'),
    url(r'^add-trainer/', views.add_trainer, name='add-trainer'),
    url(r'^reset-password/', views.reset_password, name='reset-password')


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)