
from rest_framework import serializers
from quizzes.models import Quiz, Question, Option, StudentQuizAttempt, StudentQuizAnswer


# ── Quiz Serializers ─────────────────────────────────────────────────────────

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct', 'created_at']
        read_only_fields = ['id', 'created_at']


class OptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'quiz', 'text', 'order', 'options', 'created_at']
        read_only_fields = ['id', 'quiz', 'order', 'options', 'created_at']


class QuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'order', 'created_at']
        read_only_fields = ['id', 'order', 'created_at']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ['id', 'lesson', 'description', 'questions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'lesson', 'questions', 'created_at', 'updated_at']


class QuizCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuizUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'description', 'updated_at']
        read_only_fields = ['id', 'updated_at']


# ── StudentQuizAttempt and StudentQuizAnswer Serializers ─────────────────────

class StudentQuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAnswer
        fields = [
            'id',
            'attempt',
            'question',
            'option',
            'is_correct',
            'created_at',
        ]
        read_only_fields = ['id', 'attempt', 'is_correct', 'created_at']


class StudentQuizAnswerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAnswer
        fields = ['option']


class StudentQuizAttemptSerializer(serializers.ModelSerializer):
    answers = StudentQuizAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = StudentQuizAttempt
        fields = [
            'id',
            'student',
            'quiz',
            'attempt_number',
            'started_at',
            'submitted_at',
            'score',
            'total_questions',
            'answers',
            'created_at',
        ]
        read_only_fields = [
            'id', 'student', 'quiz', 'attempt_number',
            'started_at', 'score', 'total_questions', 'answers', 'created_at',
        ]


class StudentQuizAttemptCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAttempt
        fields = ['id', 'started_at', 'created_at']
        read_only_fields = ['id', 'started_at', 'created_at']
