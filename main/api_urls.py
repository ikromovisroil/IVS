from rest_framework.routers import DefaultRouter
from .api_views import *

router = DefaultRouter()
router.register('organization', OrganizationViewSet)
router.register('department', DepartmentViewSet)
router.register('directorate', DirectorateViewSet)
router.register('division', DivisionViewSet)
router.register('rank', RankViewSet)
router.register('structure', StructureViewSet)
router.register('employee', EmployeeViewSet)
router.register('category', CategoryViewSet)
router.register('technics', TechnicsViewSet)
router.register('material', MaterialViewSet)
router.register('topic', TopicViewSet)
router.register('goal', GoalViewSet)
router.register('order', OrderViewSet)
router.register('order-material', OrderMaterialViewSet)
router.register('deed', DeedViewSet)

urlpatterns = router.urls
