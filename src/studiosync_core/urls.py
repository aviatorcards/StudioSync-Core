from django.urls import include, path

urlpatterns = [
    path('auth/', include('studiosync_core.auth.urls')),
    path('core/', include('studiosync_core.core.urls')),
    path('students/', include('studiosync_core.students.urls')),
    path('lessons/', include('studiosync_core.lessons.urls')),
    path('billing/', include('studiosync_core.billing.urls')),
    path('resources/', include('studiosync_core.resources.urls')),
    path('messaging/', include('studiosync_core.messaging.urls')),
    path('inventory/', include('studiosync_core.inventory.urls')),
    path('notifications/', include('studiosync_core.notifications.urls')),
]
