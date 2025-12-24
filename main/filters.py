import django_filters
from .models import *

# ---- EMPLOYEE FILTER ---- #
class EmployeeFilter(django_filters.FilterSet):
    # related fields
    organization = django_filters.NumberFilter(field_name='organization_id')
    department = django_filters.NumberFilter(field_name='department_id')
    directorate = django_filters.NumberFilter(field_name='directorate_id')
    division = django_filters.NumberFilter(field_name='division_id')
    structure = django_filters.NumberFilter(field_name='structure_id')
    rank = django_filters.NumberFilter(field_name='rank_id')

    # search by full name
    fullname = django_filters.CharFilter(method='filter_fullname')

    class Meta:
        model = Employee
        fields = ['status']

    def filter_fullname(self, queryset, name, value):
        return queryset.filter(
            user__first_name__icontains=value
        ) | queryset.filter(
            user__last_name__icontains=value
        )



class TechnicsFilter(django_filters.FilterSet):
    organization = django_filters.NumberFilter(field_name='employee__organization_id')
    department = django_filters.NumberFilter(field_name='employee__department_id')
    directorate = django_filters.NumberFilter(field_name='employee__directorate_id')
    division = django_filters.NumberFilter(field_name='employee__division_id')
    structure = django_filters.NumberFilter(field_name='employee__structure_id')
    category = django_filters.NumberFilter(field_name='category_id')

    class Meta:
        model = Technics
        fields = ['status', 'year']

