from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('regions', RegionViewSet, basename='region')
router.register('departments', DepartmentViewSet, basename='department')
router.register('directorates', DirectorateViewSet, basename='directorate')
router.register('divisions', DivisionViewSet, basename='division')
router.register('groups', GroupViewSet, basename='group')
router.register('contracts', ContractViewSet, basename='contract')
router.register('categories', CategoryViewSet, basename='category')
router.register('technics', TechnicsViewSet, basename='technics')
router.register('structure-categories', StructureCategoryViewSet, basename='structurecategory')
router.register('structures', StructureViewSet, basename='structure')
router.register('units', UnitViewSet, basename='unit')
router.register('material-categories', MaterialCategoryViewSet, basename='materialcategory')
router.register('materials', MaterialViewSet, basename='material')
router.register('material-employees', MaterialEmployeeViewSet, basename='materialemployee')
router.register('goals', GoalViewSet, basename='goal')
router.register('orders', OrderViewSet, basename='order')
router.register('order-goals', OrderGoalViewSet, basename='ordergoal')
router.register('material-users', MaterialUserViewSet, basename='materialuser')
router.register('deeds', DeedViewSet, basename='deed')
router.register('deed-consents', DeedConsentViewSet, basename='deedconsent')
router.register('liables', LiableViewSet, basename='liable')
router.register('material-movements', MaterialMovementViewSet, basename='materialmovement')

urlpatterns = router.urls