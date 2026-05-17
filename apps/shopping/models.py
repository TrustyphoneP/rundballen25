from django.db import models
from django.utils import timezone
import csv
import io
from decimal import Decimal


class ShoppingList(models.Model):
    camp         = models.ForeignKey("camps.Camp", on_delete=models.CASCADE, related_name="shopping_lists")
    from_date    = models.DateField(verbose_name="Von Datum")
    to_date      = models.DateField(verbose_name="Bis Datum")
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-generated_at"]
        verbose_name = "Einkaufsliste"
        verbose_name_plural = "Einkaufslisten"

    def regenerate(self):
        """Berechnet alle Items aus dem WarmMeal-Plan neu."""
        from apps.meals.models import DayMeal
        from decimal import Decimal

        meals = DayMeal.objects.filter(
            day__camp=self.camp,
            day__date__gte=self.from_date,
            day__date__lte=self.to_date,
        ).select_related("main_course", "dessert", "salad", "day")

        aggregated = {}  # (ingredient_id, unit) -> total_amount
        for meal in meals:
            for item in meal.get_all_scaled_ingredients():
                key = (item["ingredient"].id, item["unit"])
                if key not in aggregated:
                    aggregated[key] = {
                        "ingredient": item["ingredient"],
                        "unit": item["unit"],
                        "amount": Decimal("0"),
                    }
                aggregated[key]["amount"] += Decimal(str(item["amount"]))

        self.items.all().delete()
        ShoppingItem.objects.bulk_create([
            ShoppingItem(
                shopping_list=self,
                ingredient=v["ingredient"],
                amount=v["amount"],
                unit=v["unit"],
            )
            for v in aggregated.values()
        ])

    def to_csv(self):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Zutat", "Menge", "Einheit", "Gekauft"])
        for item in self.items.select_related("ingredient").order_by("ingredient__name"):
            writer.writerow([
                item.ingredient.name,
                str(item.amount).replace(".", ","),
                item.unit,
                "[ ]",
            ])
        return output.getvalue()

    def __str__(self):
        return f"Einkaufsliste {self.camp} ({self.from_date}–{self.to_date})"


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    ingredient    = models.ForeignKey("recipes.Ingredient", on_delete=models.PROTECT)
    amount        = models.DecimalField(max_digits=12, decimal_places=3)
    unit          = models.CharField(max_length=10)
    is_bought     = models.BooleanField(default=False, verbose_name="Gekauft")
    notes         = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["ingredient__name"]
        verbose_name = "Einkaufsposten"
        verbose_name_plural = "Einkaufsposten"

    def __str__(self):
        return f"{self.amount} {self.unit} {self.ingredient.name}"
