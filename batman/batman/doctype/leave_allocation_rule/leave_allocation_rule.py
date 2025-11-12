# Copyright (c) 2025, sam  and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe.utils import add_years, getdate, nowdate, date_diff, add_months


class LeaveAllocationRule(Document):
	pass


def daily_auto_leave_allocation():
    """
    Daily scheduler that allocates leaves automatically based on Leave Allocation Rule.
    Works only for specific employee types: Regular, Contract, Young Professional, Management Trainee.
    """

    today = getdate(nowdate())
    employees = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")

    # Allowed employee types
    allowed_emp_types = ["Regular", "Contract", "Young Professional", "Management Trainee"]

    for emp_name in employees:
        emp = frappe.get_doc("Employee", emp_name)
        emp_type = emp.employment_type  # or emp.custom_employee_type if using custom field

        # Skip if employee type is not in allowed list
        if emp_type not in allowed_emp_types:
            continue

        doj = emp.date_of_joining
        contract_end = emp.contract_end_date
        service_days = date_diff(today, doj) if doj else 0

        if not doj:
            continue  # skip employees without joining date

        # Fetch rules dynamically for this employee type
        rules = frappe.get_all(
            "Leave Allocation Rule",
            filters={"employee_type": emp_type},
            fields=[
                "leave_type",
                "days",
                "applicability_condition",
                "minimum_service_days",
                "valid_from",
                "valid_to",
                "contract_period",
            ],
        )

        if not rules:
            continue  # no rule found for this employee type

        for rule in rules:
            leave_type = rule.leave_type
            days = rule.days or 0
            condition = rule.applicability_condition
            min_service_days = rule.minimum_service_days or 0


           # Skip rules that are not applicable based on employee type
            if (emp_type != "Regular" and condition != "Contract Period") or (emp_type == "Regular" and condition == "Contract Period"):
                continue

            
            # # Skip if employee hasn't completed minimum service requirement
            # if service_days < min_service_days:
            #     continue

            # --- Calculate dynamic date range ---
            from_date, to_date = get_allocation_period(emp, rule, today)

            if not from_date or not to_date:
                continue

            # Prevent duplicate allocations
            existing = frappe.db.exists(
                "Leave Allocation",
                {
                    "employee": emp.name,
                    "leave_type": leave_type,
                    "from_date": from_date,
                    "to_date": to_date,
                },
            )
            if existing:
                continue  # skip duplicates

            # --- Create new Leave Allocation ---
            allocation = frappe.new_doc("Leave Allocation")
            allocation.employee = emp.name
            allocation.leave_type = leave_type
            allocation.from_date = from_date
            allocation.to_date = to_date
            allocation.new_leaves_allocated = days
            allocation.save(ignore_permissions=True)
            allocation.submit()

            frappe.logger().info(
                f"[Auto Allocation] {emp.employee_name} | {emp_type} | {leave_type} | {days} days | {from_date} to {to_date}"
            )

    frappe.db.commit()



def get_allocation_period(emp, rule, today):
    """
    Return (from_date, to_date) dynamically based on employee type and rule condition.
    """
    doj = getdate(emp.date_of_joining)
    year = today.year
    contract_end = emp.contract_end_date
    condition = rule.applicability_condition or None
    emp_type = emp.employment_type  # or emp.custom_employee_type


    # -------------------------
    # Regular employee rules
    # -------------------------
    if emp_type == "Regular":
        if condition == "First Half (Jan–Jun)":
            return getdate(f"{year}-01-01"), getdate(f"{year}-06-30")

        elif condition == "Second Half (Jul–Dec)":
            return getdate(f"{year}-07-01"), getdate(f"{year}-12-31")

        elif condition == "After 1 Year of Service":
            one_year_completion = add_years(doj, 1)

            if today < one_year_completion:
                # Not yet completed 1 year of service
                return None, None

            # Calculate how many years have been completed
            years_completed = (today.year - doj.year)

            # The allocation starts from the last completion anniversary
            from_date = add_years(doj, years_completed)
            to_date = getdate(f"{year}-12-31")

            return from_date, to_date

    # -------------------------
    # Contract / Young Professional / Management Trainee
    # -------------------------
    if emp_type != "Regular":
        if condition == "Contract Period":
            if contract_end:
                return doj, contract_end
            elif getattr(emp, "custom_contract_period", None):
                months = int(emp.custom_contract_period)
                return doj, add_months(doj, months)
            elif rule.contract_period:
                months = int(rule.contract_period)
                return doj, add_months(doj, months)
            # Default fallback: 12 months from joining
            return doj, add_months(doj, 12)

    # -------------------------
    # Default fallback (safety)
    # -------------------------
    return getdate(f"{year}-01-01"), getdate(f"{year}-12-31")
