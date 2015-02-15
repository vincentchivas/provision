from django.conf.urls import patterns, include
from django.views import static


# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()


urlpatterns = patterns('',
                       (r'^admin/', include('provisionadmin.service.urls')),
                       (r'^resources/(?P<path>.*)$',
                           static.serve,
                           {'document_root': '/home/static/resources'}),)
