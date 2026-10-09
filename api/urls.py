from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .app_views import AppConfigView
from .meeting_views import MeetingCancelView, MeetingDetailView, MeetingFinishView, MeetingListCreateView
from .auth_views import LoginThrottle
from .stats_views import EmployeeStatsView, TechnicsStatsView
from .exports import (
    EmployeesExportView, MaterialReportExportView, MaterialsExportView, TechnicsExportView,
)
from .views import *
from . import chat_views as chat
from .auth_views import (
    DeviceRegisterView, DeviceUnregisterView, LogoutView, MobileLoginExchangeView, SsoCodeLoginView, mobile_login_complete, mobile_login_start,
)

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('regions', RegionViewSet, basename='region')
router.register('departments', DepartmentViewSet, basename='department')
router.register('directorates', DirectorateViewSet, basename='directorate')
router.register('divisions', DivisionViewSet, basename='division')
router.register('ranks', RankViewSet, basename='rank')
router.register('employees', EmployeeViewSet, basename='employee')
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
router.register('order-materials', OrderMaterialViewSet, basename='ordermaterial')
router.register('order-goals', OrderGoalViewSet, basename='ordergoal')
router.register('material-users', MaterialUserViewSet, basename='materialuser')
router.register('deeds', DeedViewSet, basename='deed')
router.register('deed-files', DeedFilesViewSet, basename='deedfiles')
router.register('deed-consents', DeedConsentViewSet, basename='deedconsent')
router.register('deed-registry', DeedRegistryViewSet, basename='deedregistry')
router.register('liables', LiableViewSet, basename='liable')
router.register('material-movements', MaterialMovementViewSet, basename='materialmovement')

urlpatterns = router.urls + [
    path('me/', MeView.as_view(), name='me'),
    path('stats/technics/', TechnicsStatsView.as_view(), name='api_stats_technics'),
    path('stats/employees/', EmployeeStatsView.as_view(), name='api_stats_employees'),
    path('permissions/catalog/', PermissionCatalogView.as_view(), name='api_permission_catalog'),
    path('app/config/', AppConfigView.as_view(), name='api_app_config'),
    path('meetings/', MeetingListCreateView.as_view(), name='api_meetings'),
    path('meetings/<int:pk>/', MeetingDetailView.as_view(), name='api_meeting_detail'),
    path('meetings/<int:pk>/cancel/', MeetingCancelView.as_view(), name='api_meeting_cancel'),
    path('meetings/<int:pk>/finish/', MeetingFinishView.as_view(), name='api_meeting_finish'),
    path('token/', TokenObtainPairView.as_view(throttle_classes=[LoginThrottle]), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('export/employees.xlsx', EmployeesExportView.as_view(), name='api_export_employees'),
    path('export/material-report.xlsx', MaterialReportExportView.as_view(), name='api_export_material_report'),
    path('export/technics.xlsx', TechnicsExportView.as_view(), name='api_export_technics'),
    path('export/materials.xlsx', MaterialsExportView.as_view(), name='api_export_materials'),
    path('auth/mobile/start/', mobile_login_start, name='mobile_login_start'),
    path('auth/mobile/complete/', mobile_login_complete, name='mobile_login_complete'),
    path('auth/mobile/exchange/', MobileLoginExchangeView.as_view(), name='mobile_login_exchange'),
    path('auth/sso/token/', SsoCodeLoginView.as_view(), name='sso_code_login'),
    path('auth/logout/', LogoutView.as_view(), name='api_logout'),
    path('devices/', DeviceRegisterView.as_view(), name='api_device_register'),
    path('devices/unregister/', DeviceUnregisterView.as_view(), name='api_device_unregister'),
    path('chat/conversations/', chat.ConversationsView.as_view(), name='api_chat_conversations'),
    path('chat/contacts/', chat.ContactsView.as_view(), name='api_chat_contacts'),
    path('chat/open/', chat.OpenConversationView.as_view(), name='api_chat_open'),
    path('chat/groups/', chat.CreateGroupView.as_view(), name='api_chat_create_group'),
    path('chat/conversations/<int:pk>/messages/', chat.MessagesView.as_view(), name='api_chat_messages'),
    path('chat/conversations/<int:pk>/send/', chat.SendMessageView.as_view(), name='api_chat_send'),
    path('chat/conversations/<int:pk>/hide/', chat.HideConversationView.as_view(), name='api_chat_hide'),
    path('chat/conversations/<int:pk>/members/', chat.GroupMembersView.as_view(), name='api_chat_members'),
    path('chat/conversations/<int:pk>/members/add/', chat.GroupAddMembersView.as_view(), name='api_chat_members_add'),
    path('chat/conversations/<int:pk>/members/<int:member_id>/remove/', chat.GroupRemoveMemberView.as_view(), name='api_chat_member_remove'),
    path('chat/conversations/<int:pk>/members/<int:member_id>/admin/', chat.GroupSetAdminView.as_view(), name='api_chat_member_admin'),
    path('chat/messages/<int:pk>/edit/', chat.EditMessageView.as_view(), name='api_chat_edit'),
    path('chat/messages/<int:pk>/delete/', chat.DeleteMessageView.as_view(), name='api_chat_delete'),
    path('chat/unread-count/', chat.UnreadCountView.as_view(), name='api_chat_unread'),
    path('chat/ping/', chat.PingView.as_view(), name='api_chat_ping'),

]
