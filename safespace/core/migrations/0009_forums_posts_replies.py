import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_old_forums_to_posts(apps, schema_editor):
    """
    The old Forum model was really one post: copy each row into Post.
    """

    OldForum = apps.get_model("core", "Forum")
    Post = apps.get_model("core", "Post")

    for old in OldForum.objects.all():
        Post.objects.create(
            id=old.id,
            user_id=old.user_id,
            group=old.group,
            content=old.content,
            location=old.location,
        )
        # auto_now_add sets "now" on create, so restore the original time
        Post.objects.filter(id=old.id).update(created_at=old.created_at)


def copy_posts_to_old_forums(apps, schema_editor):
    OldForum = apps.get_model("core", "Forum")
    Post = apps.get_model("core", "Post")

    for post in Post.objects.all():
        OldForum.objects.create(
            id=post.id,
            user_id=post.user_id,
            group=post.group,
            content=post.content,
            location=post.location,
        )
        OldForum.objects.filter(id=post.id).update(created_at=post.created_at)


def groups_to_forums(apps, schema_editor):
    """
    Turn each existing post's group name into a Forum.
    The first poster becomes its creator, and every poster becomes a member.
    """

    Forum = apps.get_model("core", "Forum")
    Post = apps.get_model("core", "Post")

    for post in Post.objects.order_by("created_at"):
        forum, _ = Forum.objects.get_or_create(
            name=post.group,
            defaults={"location": post.location, "created_by": post.user},
        )
        forum.members.add(post.user)

        post.forum = forum
        post.save(update_fields=["forum"])


def forums_to_groups(apps, schema_editor):
    Post = apps.get_model("core", "Post")

    for post in Post.objects.select_related("forum"):
        post.group = post.forum.name
        post.save(update_fields=["group"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_more_quests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # The old Forum model was really one post: move its rows into Post.
        # (Copying instead of RenameModel avoids permission clashes with an
        # older "post" model in existing databases.)
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("group", models.CharField(
                    default="",
                    help_text="Community or group that this post belongs to.",
                    max_length=120,
                )),
                ("content", models.TextField()),
                ("location", models.CharField(
                    blank=True,
                    help_text="Optional city or area associated with the post.",
                    max_length=100,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="forum_posts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(copy_old_forums_to_posts, copy_posts_to_old_forums),
        migrations.DeleteModel(name="Forum"),

        # Forum is now the community that users join
        migrations.CreateModel(
            name="Forum",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("category", models.CharField(
                    choices=[
                        ("learning", "Learning"),
                        ("budgeting", "Budgeting"),
                        ("diet", "Diet & Wellness"),
                        ("social", "Social"),
                        ("general", "General Self-Care"),
                        ("exploration", "Exploration"),
                        ("other", "Other"),
                    ],
                    default="general",
                    max_length=20,
                )),
                ("location", models.CharField(
                    blank=True,
                    help_text='Optional "City, ST" (e.g. "Champaign, IL"), used by Forums Nearby.',
                    max_length=100,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="forums_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("members", models.ManyToManyField(
                    blank=True,
                    related_name="forums",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["name"],
            },
        ),

        # Link posts to forums, move the data, then drop the old group text
        migrations.AddField(
            model_name="post",
            name="forum",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posts",
                to="core.forum",
            ),
        ),
        migrations.RunPython(groups_to_forums, forums_to_groups),
        migrations.RemoveField(
            model_name="post",
            name="group",
        ),
        migrations.AlterField(
            model_name="post",
            name="forum",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posts",
                to="core.forum",
            ),
        ),

        migrations.CreateModel(
            name="Reply",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="replies",
                    to="core.post",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="forum_replies",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name_plural": "replies",
                "ordering": ["created_at"],
            },
        ),
    ]
