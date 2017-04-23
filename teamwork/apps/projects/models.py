"""
Teamwork: projects

Database Models for the objects, Project, Membership, Intrest, ProjectUpdate
"""

# Built-in modules
from __future__ import unicode_literals
from datetime import datetime
import random
import string

# Django modules
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
import numpy as np

# Not used currently
from django.db.models import Q

# Third-party Modules
import markdown

# Local Modules
from teamwork.apps.profiles.models import *
# from teamwork.apps.courses.models import Course
# can't do this, would cause dependency loop :(


# Generates add code
def rand_code(size):
    # Usees a random choice from lowercase, uppercase, and digits
    return ''.join([
        random.choice(string.ascii_letters + string.digits) for i in range(size)
    ])



# Model definitions for the core app.
# As we move forward, the core app will likely disapear. It's mainly for testing everything out right now.
class Interest(models.Model):
    """
    Intrest object relates a user to a intrest (may be changed in the future)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interest = models.PositiveIntegerField()
    interest_reason = models.CharField(max_length=100)


class Project(models.Model):
    """
    Project: A database model (object) for projects.

    Fields:
        title: the title of the project.

    Methods:
        __str__(self):                  Human readeable representation of the Project object.
        save(self, *args, **kwargs):    Overides the default save operator...
        get_published():                Gets a list of all stored Project objects.

    """

    # The title of the project. Should not be null, but default is provided.
    title = models.CharField(
        max_length=255, default="No Project Title Provided")
    # TODO: This should not be a CharField
    creator = models.CharField(max_length=255, default="No Creator Specified")
    # Short project description
    tagline = models.TextField(max_length=38, default="Default Project Tagline")
    # Verbose project description.
    content = models.TextField(max_length=4000, default="Content")
    # Members associated with a project (Membership objects)
    members = models.ManyToManyField(User, through='Membership')
    # Skills needed for the project.
    desired_skills = models.ManyToManyField(
        Skills, related_name="desired", default="")
    # True when the proejct is accepting new members. False when project is full.
    avail_mem = models.BooleanField(default=True)
    # True when project is sponsered. False when project is not sponsered. Field hidden to students.
    sponsor = models.BooleanField(default=False)
    # Unique URL slug for project
    slug = models.CharField(max_length=20, unique=True)
    # Resource list that the project members can update
    resource = models.TextField(
        max_length=4000, default="*No resources provided*")

    interest = models.ManyToManyField(Interest, default='')
    # Date the project was originally submitted on
    # Commented until we get to a point where we want to have everyone flush
    #create_date = models.DateTimeField(auto_now_add=True)

    weigh_interest = models.IntegerField(default=1)
    weigh_know = models.IntegerField(default=1)
    weigh_learn = models.IntegerField(default=1)

    # The Meta class provides some extra information about the Project model.
    class Meta:
        # Verbose name is the same as class name in this case.
        verbose_name = "Project"
        # Multiple Project objects are referred to as Projects.
        verbose_name_plural = "Projects"

    def __str__(self):
        """
        Human readeable representation of the Project object. Might need to update when we add more attributes.
        Maybe something like, return u'%s %s' % (self.course, self.title)
        """
        return self.title

    def save(self, *args, **kwargs):
        """
        Overides the default save operator...
        Bassically a way to check if the Project object exists in the database. Will be helpful later.
        self.pk is the primary key of the Project object in the database!
        """
        #if not self.pk:
        #    super(Project, self).save(*args, **kwargs)

        # Generate a Project URL slug if not specified
        #     Based off Courses.save URL slug written by August
        if self.slug is None or len(self.slug) == 0:
            # Basing the slug off of project title. Possibly change in the future.
            newslug = self.title
            newslug = slugify(newslug)[0:20]
            while Project.objects.filter(slug=newslug).exists():
                print(Project.objects.filter(slug=newslug).exists())
                newslug = self.title
                newslug = slugify(newslug[0:16] + "-" + rand_code(3))
            self.slug = newslug

        self.slug = slugify(self.slug)

        super(Project, self).save(*args, **kwargs)

    # Given an array, creates a bitstring based on meeting times
    def to_bits(day):
        # Creates array of all 0's of length 48
        bitstring = [False]*48

        # Loops through each Event in array
        for event in day:
            # Start time - End time to get # of slots to block off
            diff = event.end_time_hour - event.start_time_hour
            # Doubles because we are using 30 minute intervals
            diff *= 2
            # Blocks off times
            for i in diff:
                bitstring[(event.start_time_hour - 1) + i] = True
            # If we ended in XX:30, block off next bit
            if event.end_time_min == 30:
                bitstring[event.end_time_hour] = True

        # Manually block off 12a - 8a and 10p - 12a
        for x in range(0, 16):
            bitstring[x] = True
        for x in range(44, 47):
            bitstring[x] = True

        return bitstring

    #given a bitstring, converts to array containing start and end time
    def from_bits(bitstring):
        event_array = []
        temp = 0
        start_hour = 0
        start_min = 0
        end_hour = 0
        end_minute = 0

        # For each index in bitstring
        for i in bitstring:
            # If current index is False (Free)
            if bitstring[i] is False:
                # If odd, start at xx:30
                if i % 2 != 0:
                    start_min = 30
                # Start hour is i/2
                start_hour = floor(i/2)

                # Loops until True (Busy)
                temp = i
                while bitstring[temp] == False:
                    # If next element is True (Busy), we are at end of time slot
                    if bitstring[temp + 1] == True:
                        # Update i
                        i = temp
                        # If odd, end at xx:30
                        if i % 2 != 0:
                            end_min = 30
                        # End hour is i/2
                        end_hour = floor(i/2)
                    # Increase temp
                    temp++
                event_array.append([start_hour, start_min, end_hour, end_min])

        return event_array
    # Generates a list of possible avalibilities and stores in current project's avalibiltiy
    def generate_avail(self):
        event_list = []     # list of all events for each user
        pos_event = []      # list of possible meeting times
        temp = []

        sunday_list = []
        sunday_post = []

        monday_list = []
        monday_post = []

        teusday_list = []
        teusday_post = []

        wednesday_list = []
        wednesday_post=[]

        thursday_list = []
        thursday_post = []

        friday_list = []
        friday_post = []

        saturday_list = []
        saturday_post = []

        # Loops through each member
        for user in self.members:
            # Loops through each event
            for event in user.avail:
                # adds to list
                event_list.append(user.avail)

        # Sorts each event into respective days
        for i in event_list:
            if i.day == "Sunday":
                sunday_list.append(i)
            if i.day == "Monday":
                monday_list.append(i)
            if i.day == "Teusday":
                teusday_list.append(i)
            if i.day == "Wednesday":
                wednesday_list.append(i)
            if i.day == "Thursday":
                thursday_list.append(i)
            if i.day == "Friday":
                friday_list.append(i)
            if i.day == "Saturday":
                saturday_list.append(i)

            # Converts to and from bitstring to find FREE time
            sunday_list = to_bits(sunday_list)
            sunday_list = from_bits(sunday_list)
            # Appends to list
            for i in sunday_list:
                pos_event.append(["Sunday", i[0], i[1], i[2], i[3]])

            monday_list = to_bits(monday_list)
            monday_list = from_bits(monday_list)
            for i in monday_list:
                pos_event.append(["Monday", i[0], i[1], i[2], i[3]])

            teusday_list = to_bits(teusday_list)
            teusday_list = from_bits(teusday_list)
            for i in teusday_list:
                pos_event.append(["Teusday", i[0], i[1], i[2], i[3]])

            wednesday_list = to_bits(wednesday_list)
            wednesday_list = from_bits(wednesday_list)
            for i in wednesday_list:
                pos_event.append(["Wednesday", i[0], i[1], i[2], i[3]])

            thursday_list = to_bits(thursday_list)
            thursday_list = from_bits(thursday_list)
            for i in thursday_list:
                pos_event.append(["Thursday", i[0], i[1], i[2], i[3]])

            friday_list = to_bits(friday_list)
            friday_list = from_bits(friday_list)
            for i in friday_list:
                pos_event.append(["Friday", i[0], i[1], i[2], i[3]])

            saturday_list = to_bits(saturday_list)
            saturday_list = from_bits(saturday_list)
            for i in saturday_list:
                pos_event.append(["Saturday", i[0], i[1], i[2], i[3]])

        # Returns list of possible events
        return pos_event

    @staticmethod
    def get_my_projects(user):
        """
        Gets a list of project objects. Used in views then passed to the template.
        """
        #Gets membership object of current user
        myProjects = Membership.objects.filter(user=user)
        #Gets project queryset of only projects user is in OR the user created
        proj = Project.objects.filter(membership__in=myProjects)

        return proj

    def get_all_projects():
        """
        Gets a list of project objects. Used in views then passed to the template.
        """
        projects = Project.objects.filter()
        return projects

    def get_created_projects(user):
        """
        Gets a list of porject objects that the user created. Used in views then passed to the template
        """
        proj = Project.objects.filter(creator=user.username)
        return proj

    def get_content_as_markdown(self):
        return markdown.markdown(self.content, safe_mode='escape')

    def get_resource_as_markdown(self):
        return markdown.markdown(self.resource, safe_mode='escape')

    def get_updates(self):
        return ProjectUpdate.objects.filter(project=self)

    """ Unfortunately not possible due to dependency loop
    def course(self):
        return next(course for course in Course.objects.all() if this in
                course.projects.all())
    """

class Membership(models.Model):
    """
    Membership objects relate a user and a project.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=0)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, default=0)
    invite_reason = models.CharField(max_length=64)


class ProjectUpdate(models.Model):
    """
    ProjectUpdate objects are updates associated with a project

    Attributes:
        project: ForeignKey to the project, found by project slug
        update_title: The title of a project update
        update: The content of the project update
        date: Date that the project update was posted
        user: The currently logged in user (associated with the project update)

    """
    project = models.ForeignKey(Project)
    update_title = models.CharField(
        max_length=255, default="Default Update Title")
    update = models.TextField(max_length=2000, default="Default Update")
    date = models.DateTimeField(auto_now_add=True, editable=True)
    user = models.ForeignKey(User)

    class Meta:
        verbose_name = "Project Update"
        verbose_name_plural = "Project Updates"
        ordering = ("-date", )

    def __str__(self):
        return '{0} - {1}'.format(self.user.username, self.project.title)


# project status: open/closed and number available
# currently commented to avoid conflict with other files
"""
class Project_Status (Project):

    #numerical ranges for number of members in a group
    SIX = 6
    FIVE = 5
    FOUR = 4
    THREE = 3
    TWO = 2
    ONE = 1
    ZERO = 0
    MAX_CHOICES = (
        (SIX,'Six'),
        (FIVE,'Five'),
    )
    NUM_CHOICES = (
        (FIVE,'Five'),
        (FOUR,'Four'),
        (THREE,'Three'),
        (TWO,'Two'),
        (ONE,'One'),
        (ZERO,'Zero'),
    )

    # max_cap = maximum number of members in a group
    # current_mem = number of members currently in a group
    # need_mem = number of members needed in a group
    # avail_mem = determine open/closed status of a project
    max_cap = models.PositiveIntegerField(choices = MAX_CHOICES)PositiveIntegerField
    current_mem = models.PositiveIntegerField(default = 1, choices = NUM_CHOICES)
    need_mem = models.PositiveIntegerField(choices = NUM_CHOICES)
    avail_mem = models.BooleanField(default = True)

    def remain(self):
        self.need_mem = {{self.max_cap|sub: self.current_mem}}
        self.avail_mem = case(when(self.need_mem = 0, then = False))

"""
