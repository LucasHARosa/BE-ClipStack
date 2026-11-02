from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Só para o frontend decidir o que mostrar; o backend nunca autoriza pelo claim.
        token["role"] = user.role
        token["username"] = user.username
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "password", "password_confirm")
        # role read-only: ninguém se cadastra como ADMIN.
        read_only_fields = ("id", "role")

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas não conferem."})

        candidate = User(email=attrs["email"], username=attrs["username"])
        try:
            password_validation.validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            # A ValidationError do Django viraria 500.
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    # create_user() faz o hash da senha; o create() padrão gravaria o texto puro.
    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "date_joined")
        # email é a credencial de login: trocar exigiria um fluxo com confirmação.
        read_only_fields = ("id", "email", "role", "date_joined")


class AdminUserSerializer(serializers.ModelSerializer):
    # Vem do annotate() do queryset.
    videos_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "role",
            "is_active",
            "date_joined",
            "last_login",
            "videos_count",
        )
        read_only_fields = fields


class SetRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)
