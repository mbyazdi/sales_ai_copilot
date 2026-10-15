from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_requests", "0002_salesrequestmutationreceipt")]

    operations = [
        migrations.RemoveConstraint(
            model_name="salesrequestmutationreceipt", name="srmr_valid_operation",
        ),
        migrations.AlterField(
            model_name="salesrequestmutationreceipt", name="operation",
            field=models.CharField(max_length=24, choices=[
                ("ADD_PRODUCT", "افزودن محصول"),
                ("SET_QUANTITY", "تغییر تعداد"),
                ("REMOVE_PRODUCT", "حذف محصول"),
                ("REJECT_RECOMMENDATION", "رد پیشنهاد"),
                ("COMPLETE_VISIT", "پایان ویزیت"),
            ]),
        ),
        migrations.AddConstraint(
            model_name="salesrequestmutationreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(operation__in=[
                    "ADD_PRODUCT", "SET_QUANTITY", "REMOVE_PRODUCT",
                    "REJECT_RECOMMENDATION", "COMPLETE_VISIT",
                ]), name="srmr_valid_operation",
            ),
        ),
    ]
