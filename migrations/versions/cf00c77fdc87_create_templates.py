"""create templates

Revision ID: cf00c77fdc87
Revises: 5c7ba231252f
Create Date: 2024-10-22 00:20:19.788098

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf00c77fdc87'
down_revision = '5c7ba231252f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('template_exercise')
    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.drop_constraint('exercise_id_key', type_='unique')
        batch_op.create_unique_constraint(None, ['name'])

    with op.batch_alter_table('workout_template', schema=None) as batch_op:
        batch_op.drop_column('description')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('workout_template', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True))

    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_unique_constraint('exercise_id_key', ['id'])

    op.create_table('template_exercise',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('template_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('exercise_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('sets', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('reps', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['exercise_id'], ['exercise.id'], name='template_exercise_exercise_id_fkey'),
    sa.ForeignKeyConstraint(['template_id'], ['workout_template.id'], name='template_exercise_template_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='template_exercise_pkey')
    )
    # ### end Alembic commands ###
