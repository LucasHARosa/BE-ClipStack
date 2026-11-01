from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    # ModelSerializer: gera os campos e as validações a partir do model (max_length, unique...).
    # email e username são unique=True no model, então o DRF adiciona um UniqueValidator
    # sozinho: email repetido vira 400 com mensagem no campo, sem escrever nada.

    # write_only: o campo entra na requisição mas nunca aparece na resposta.
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    # Campo que não existe no model: só serve para validação e é descartado no create().
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "password", "password_confirm")
        # read_only_fields: aparecem na resposta, mas são ignorados se vierem na entrada.
        # role read-only é o que impede alguém de se cadastrar como ADMIN.
        read_only_fields = ("id", "role")

    # validate(): validação entre campos. Roda depois de todas as validações de campo.
    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas não conferem."})

        # Validadores do AUTH_PASSWORD_VALIDATORS (tamanho mínimo, senha comum, parecida com
        # o email...). Recebem um User não salvo para comparar com os outros campos.
        candidate = User(email=attrs["email"], username=attrs["username"])
        try:
            password_validation.validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            # O DRF só converte em 400 a ValidationError DELE; a do Django viraria 500.
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    # create() sobrescrito: o padrão chamaria User.objects.create(password="texto puro").
    # create_user() faz o hash da senha. Se o cadastro ganhar regras (email de boas-vindas,
    # convite, auditoria), isso sai daqui e vai para um service.
    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    # GET/PATCH /users/me/. Só o username é editável.
    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "date_joined")
        # email: é a credencial de login; trocar exige um fluxo próprio (confirmação).
        # role: o próprio usuário nunca muda o seu papel (escalada de privilégio).
        read_only_fields = ("id", "email", "role", "date_joined")


class AdminUserSerializer(serializers.ModelSerializer):
    # Saída da área admin (/admin/users/). videos_count vem de um annotate() no queryset.
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
    # Serializer puro (não ModelSerializer): valida a entrada de uma AÇÃO, não de um recurso.
    # Quem aplica a mudança é o service (que também sincroniza is_staff via save()).
    role = serializers.ChoiceField(choices=User.Role.choices)
