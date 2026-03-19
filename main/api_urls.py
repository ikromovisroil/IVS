from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .api_views import *

router = DefaultRouter()

router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'directorates', DirectorateViewSet, basename='directorate')
router.register(r'divisions', DivisionViewSet, basename='division')
router.register(r'ranks', RankViewSet, basename='rank')
router.register(r'regions', RegionViewSet, basename='region')
router.register(r'roles', RolViewSet, basename='role')
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'technics', TechnicsViewSet, basename='technics')
router.register(r'structure-categories', StructureCategoryViewSet, basename='structure-category')
router.register(r'structures', StructureViewSet, basename='structure')
router.register(r'units', UnitViewSet, basename='unit')
router.register(r'material-categories', MaterialCategoryViewSet, basename='material-category')
router.register(r'materials', MaterialViewSet, basename='material')
router.register(r'goals', GoalViewSet, basename='goal')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-materials', OrderMaterialViewSet, basename='order-material')
router.register(r'deeds', DeedViewSet, basename='deed')
router.register(r'deed-consents', DeedConsentViewSet, basename='deed-consent')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'liables', LiableViewSet, basename='liable')

urlpatterns = [
    path('', include(router.urls)),
]