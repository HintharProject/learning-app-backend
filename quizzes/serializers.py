from rest_framework import serializers
from quizzes.models import Quiz, StudentQuizAttempt


class QuizSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'lesson', 'description', 'passing_percentage', 'questions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'lesson', 'created_at', 'updated_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        
        # Hide 'is_correct' if the user is a student
        if request and hasattr(request, 'user') and request.user.role == 'STUDENT':
            questions = representation.get('questions', [])
            for question in questions:
                options = question.get('options', [])
                for option in options:
                    option.pop('is_correct', None)
        return representation


class QuizCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'description', 'passing_percentage', 'questions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_questions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Questions must be a list.")
        return value


class QuizUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'description', 'passing_percentage', 'questions', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class StudentQuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAttempt
        fields = [
            'id', 'student', 'quiz', 'attempt_number',
            'started_at', 'submitted_at', 'score',
            'total_questions', 'passed', 'answers_submitted', 'created_at'
        ]
        read_only_fields = [
            'id', 'student', 'quiz', 'attempt_number',
            'started_at', 'submitted_at', 'score',
            'total_questions', 'passed', 'answers_submitted', 'created_at'
        ]


class StudentQuizAttemptCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentQuizAttempt
        fields = ['id', 'started_at', 'created_at']
        read_only_fields = ['id', 'started_at', 'created_at']
