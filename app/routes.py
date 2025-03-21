from flask import render_template, request, redirect, url_for, flash
from app import app, db
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Question, UserResponse
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, RadioField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from random import choice
from app import bcrypt

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class QuizForm(FlaskForm):
    answer = RadioField('Answer', choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], validators=[DataRequired()])
    submit = SubmitField('Submit')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login failed. Check your email and password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():
    # Get user's past performance by topic
    responses = UserResponse.query.filter_by(user_id=current_user.id).all()
    topic_stats = {}
    for r in responses:
        topic = r.question.topic
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0}
        topic_stats[topic]['total'] += 1
        if r.is_correct:
            topic_stats[topic]['correct'] += 1

    all_questions = Question.query.all()
    if not all_questions:
        flash('No questions available yet.', 'warning')
        return redirect(url_for('home'))

    # Select 3 questions, prioritizing weaker topics
    selected_questions = []
    for _ in range(3):
        if topic_stats:
            weakest_topic = min(topic_stats, key=lambda t: topic_stats[t]['correct'] / max(1, topic_stats[t]['total']))
            candidates = [q for q in all_questions if q.topic == weakest_topic and q not in selected_questions]
        else:
            candidates = [q for q in all_questions if q not in selected_questions]
        if candidates:
            selected_questions.append(choice(candidates))
        else:
            selected_questions.append(choice([q for q in all_questions if q not in selected_questions]))

    forms = [QuizForm(prefix=str(q.id)) for q in selected_questions]
    quiz_data = list(zip(selected_questions, forms))

    if request.method == 'POST':
        for question, form in quiz_data:
            if form.validate_on_submit():
                selected = form.answer.data
                is_correct = (selected == question.correct_option)
                response = UserResponse(user_id=current_user.id, question_id=question.id, 
                                        selected_option=selected, is_correct=is_correct)
                db.session.add(response)
        db.session.commit()
        flash('Quiz submitted successfully!', 'success')
        return redirect(url_for('results'))

    return render_template('quiz.html', quiz_data=quiz_data)

@app.route('/results')
@login_required
def results():
    responses = UserResponse.query.filter_by(user_id=current_user.id).order_by(UserResponse.id.desc()).limit(3).all()
    if not responses:
        flash('No quiz results found. Please take the quiz first.', 'warning')
        return redirect(url_for('quiz'))

    score = sum(1 for r in responses if r.is_correct)
    total_questions = len(responses)

    results_data = [
        {
            'question_text': r.question.question_text,
            'selected_option': f"{r.selected_option}. {getattr(r.question, f'option_{r.selected_option.lower()}')}",
            'correct_option': f"{r.question.correct_option}. {getattr(r.question, f'option_{r.question.correct_option.lower()}')}",
            'is_correct': r.is_correct,
            'explanation': r.question.explanation or "No explanation available."
        }
        for r in responses
    ]

    return render_template('results.html', score=score, total_questions=total_questions, results_data=results_data)


@app.route('/dashboard')
@login_required
def dashboard():
    responses = UserResponse.query.filter_by(user_id=current_user.id).all()
    topic_stats = {}
    for r in responses:
        topic = r.question.topic
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0}
        topic_stats[topic]['total'] += 1
        if r.is_correct:
            topic_stats[topic]['correct'] += 1
    
    for topic in topic_stats:
        topic_stats[topic]['percentage'] = (topic_stats[topic]['correct'] / topic_stats[topic]['total']) * 100
    
    return render_template('dashboard.html', topic_stats=topic_stats)