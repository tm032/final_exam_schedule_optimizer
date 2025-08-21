"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

See models.py for explanation of PreferenceProfile
This views file handles the requests to create, view, and delete PreferenceProfile objects
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from ..forms import PreferenceProfileForm
from ..models import PreferenceProfile

def create_preference_profile(request):
    if request.method == "POST":
        form = PreferenceProfileForm(request.POST)

        if form.is_valid():
            print("form is valid")
            profile = form.save(commit=False)
            if not profile.name:
                # Count the number of existing unnamed profiles
                unnamed_count = PreferenceProfile.objects.filter(name__startswith="Preference Profile ").count() + 1
                profile.name = f"Preference Profile {unnamed_count}"
            
            profile.save()
            return redirect(reverse('preference_profile_list'))
    else:
        form = PreferenceProfileForm()
    return render(request, 'optimizer/create_preference_profile.html', {'form': form})


def preference_profile_list(request):
    profiles = PreferenceProfile.objects.all()
    return render(request, 'optimizer/preference_profile_list.html', {'profiles': profiles})

def delete_preference_profile(request, pk):
    profile = get_object_or_404(PreferenceProfile, pk=pk)
    if request.method == 'POST':
        profile.delete()
        return redirect('preference_profile_list')  # Redirect to the list of profiles
    return redirect('preference_profile_list')  # Redirect in case of a GET request or any other scenario