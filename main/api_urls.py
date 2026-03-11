from rest_framework.routers import DefaultRouter
from .api_views import (
    OrganizationViewSet, DepartmentViewSet, DirectorateViewSet, DivisionViewSet,
    RankViewSet, RegionViewSet, RolViewSet, EmployeeViewSet,
    CategoryViewSet, TechnicsViewSet,
    ExtraCategoryViewSet, ExtraTechnicsViewSet,
    UnitViewSet, MaterialViewSet,
    GoalViewSet, OrderViewSet, OrderMaterialViewSet,
    DeedViewSet, DeedConsentViewSet,
    ContractViewSet, LiableViewSet
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'directorates', DirectorateViewSet)
router.register(r'divisions', DivisionViewSet)
router.register(r'ranks', RankViewSet)
router.register(r'regions', RegionViewSet)
router.register(r'roles', RolViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'technics', TechnicsViewSet)
router.register(r'extra-categories', ExtraCategoryViewSet)
router.register(r'extra-technics', ExtraTechnicsViewSet)
router.register(r'units', UnitViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'goals', GoalViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-materials', OrderMaterialViewSet)
router.register(r'deeds', DeedViewSet)
router.register(r'deed-consents', DeedConsentViewSet)
router.register(r'contracts', ContractViewSet)
router.register(r'liables', LiableViewSet)

urlpatterns = router.urls