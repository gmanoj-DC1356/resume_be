from rest_framework import serializers


class SearchRequestSerializer(serializers.Serializer):
    """Allowlist validation for the search request (camelCase to match the UI)."""

    jobTitle = serializers.CharField(max_length=200)
    skills = serializers.ListField(
        child=serializers.CharField(max_length=60), max_length=50, required=False, default=list
    )
    jobDescription = serializers.CharField(max_length=10000, required=False, allow_blank=True, default="")
    topN = serializers.IntegerField(min_value=1, max_value=50, required=False, default=10)

    def validate(self, attrs):
        if not attrs["skills"] and not attrs["jobDescription"].strip():
            raise serializers.ValidationError("Provide at least one skill or a job description.")
        return attrs
