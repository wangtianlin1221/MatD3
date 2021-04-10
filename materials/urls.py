# This file is covered by the BSD license. See LICENSE in the root directory.
from django.urls import include
from django.urls import path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register('references', views.ReferenceViewSet)
# router.register('systems', views.CompoundViewSet)
router.register('properties', views.PropertyViewSet)
router.register('units', views.UnitViewSet)
router.register('space-groups', views.SpaceGroupViewSet)
# router.register('datasets', views.DatasetViewSet)

app_name = 'materials'
urlpatterns = [
    path('', include(router.urls)),
    path('search', views.SearchFormView.as_view(), name='search'),
    path('<int:pk>', views.CompoundView.as_view(), name='compound'),
    path('dataset-versions/<int:compound_pk>/<int:property_pk>', views.dataset_versions, name='dataset_versions'),
    path('dataset-details/<int:pk>', views.dataset_details, name='dataset_details'),
#     path('dataset/<int:pk>', views.DatasetView.as_view(), name='dataset'),
#     path('dataset/<int:pk>/toggle-visibility/<str:view_name>',
#          views.toggle_visibility, name='toggle_visibility'),
    path('dataset/<int:compound_pk>/<int:dataset_pk>/delete/<str:view_name>',
         views.delete_dataset, name='delete_dataset'),
#     path('dataset/<int:pk>/verify/<str:view_name>',
#          views.verify_dataset, name='verify_dataset'),
    path('add-data', views.AddDataView.as_view(), name='add_data'),
    path('update-dataset/<int:pk>', views.UpdateDatasetView.as_view(), name='update_dataset'),
    path('import-data', views.ImportDataView.as_view(), name='import_data'),
    path('submit-data', views.submit_data, name='submit_data'),
    path('tolerance-factor', views.ToleranceFactorView.as_view(), name='tolerance_factor'),
    path('tolerance-factor-chart/<int:data_source>/<int:compound_pk>', views.data_for_tf, name='tolerance_factor_chart'),
#     path('reference/<int:pk>', views.ReferenceDetailView.as_view(),
#          name='reference'),
    path('autofill-input-data', views.autofill_input_data),
    path('data-for-chart/<int:pk>', views.data_for_chart,
         name='data_for_chart'),
#     path('get-subset-values/<int:pk>', views.get_subset_values,
#          name='get_subset_values'),
    path('get-jsmol-input/<int:pk>', views.get_jsmol_input,
         name='get_jsmol_input'),
#     path('report-issue', views.report_issue, name='report_issue'),
    # path('prefilled-form/<int:pk>', views.prefilled_form,
    #      name='prefilled_form'),
#     path('mint-doi/<int:pk>', views.MintDoiView.as_view(), name='mint_doi'),
#     path('figshare-callback', views.figshare_callback,
#          name='figshare_callback'),
]
