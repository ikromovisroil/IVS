from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Tuzilma (spravochnik)
router.register('organizations', views.OrganizationViewSet)
router.register('regions', views.RegionViewSet)
router.register('departments', views.DepartmentViewSet)
router.register('directorates', views.DirectorateViewSet)
router.register('divisions', views.DivisionViewSet)
router.register('ranks', views.RankViewSet)
router.register('groups', views.GroupViewSet)
router.register('categories', views.CategoryViewSet)
router.register('structure-categories', views.StructureCategoryViewSet)
router.register('units', views.UnitViewSet)
router.register('material-categories', views.MaterialCategoryViewSet)
router.register('goals', views.GoalViewSet)
router.register('contracts', views.ContractViewSet)

# Xodim
router.register('employees', views.EmployeeViewSet)

# Texnika
router.register('technics', views.TechnicsViewSet)
router.register('structures', views.StructureViewSet)

# Material
router.register('materials', views.MaterialViewSet)
router.register('material-employees', views.MaterialEmployeeViewSet)
router.register('material-movements', views.MaterialMovementViewSet)

# Ariza
router.register('orders', views.OrderViewSet)
router.register('order-materials', views.OrderMaterialViewSet)
router.register('order-goals', views.OrderGoalViewSet)
router.register('material-users', views.MaterialUserViewSet)

# Xujat
router.register('deeds', views.DeedViewSet)
router.register('deed-consents', views.DeedConsentViewSet)
router.register('liables', views.LiableViewSet)

urlpatterns = [
    path('', include(router.urls)),
]