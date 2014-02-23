Name:           sarstats
Version:        0.1
Release:        1%{?dist}
Summary:        Creates a performance report from sar files
License:        GPLv2
URL:            https://github.com/mbaldessari/sarstats
Source0:        sarstats-0.1.tar.gz
BuildArch:	noarch
BuildRequires:  python
Requires:       python-matplotlib
Requires:	python-reportlab
Requires:	python-numpy

%description
Generate a PDF report of one or more sar files

%prep
%setup -q


%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --skip-build --root $RPM_BUILD_ROOT

%files
%doc README LICENSE
%{_bindir}/sarstats
%{python_sitelib}/*.egg-info
%{python_sitelib}/*.py
%{python_sitelib}/*.py[oc]

%changelog
* Fri Dec 27 2013 Michele Baldessari <michele@acksyn.org> - 0.1-1
- Initial release
