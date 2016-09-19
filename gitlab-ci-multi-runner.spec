# the revision for images
%define	revision	%{version}
Summary:	The official GitLab CI runner written in Go
Name:		gitlab-ci-multi-runner
Version:	1.5.2
Release:	1
License:	MIT
Group:		Development/Building
Source0:	https://gitlab.com/gitlab-org/gitlab-ci-multi-runner/repository/archive.tar.gz?ref=v%{version}&/%{name}-%{version}.tar.gz
# Source0-md5:	3daf43173c38421fb9243fc20a7adf70
Source1:	https://gitlab-ci-multi-runner-downloads.s3.amazonaws.com/master/docker/prebuilt-x86_64.tar.xz
# Source1-md5:	0d89c7578a0b5d22a4ae85dcb7d5b4f5
Source2:	https://gitlab-ci-multi-runner-downloads.s3.amazonaws.com/master/docker/prebuilt-arm.tar.xz
# Source2-md5:	c0533c581624dcb33095f08f06e6a00b
URL:		https://gitlab.com/gitlab-org/gitlab-ci-multi-runner
BuildRequires:	git-core
BuildRequires:	go-bindata >= 3.0.7-1.a0ff2567
BuildRequires:	golang >= 1.4
BuildRequires:	rpmbuild(macros) >= 1.202
Requires(postun):	/usr/sbin/groupdel
Requires(postun):	/usr/sbin/userdel
Requires(pre):	/bin/id
Requires(pre):	/usr/bin/getgid
Requires(pre):	/usr/sbin/groupadd
Requires(pre):	/usr/sbin/useradd
Requires:	bash
Requires:	ca-certificates
Requires:	curl
Requires:	git-core
Requires:	tar
Suggests:	docker >= 1.8
Provides:	group(gitlab-runner)
Provides:	user(gitlab-runner)
ExclusiveArch:	%{ix86} %{x8664} %{arm}
BuildRoot:	%{tmpdir}/%{name}-%{version}-root-%(id -u -n)

# go stuff
%define _enable_debug_packages 0
%define gobuild(o:) go build -ldflags "${LDFLAGS:-} -B 0x$(head -c20 /dev/urandom|od -An -tx1|tr -d ' \\n')" -a -v -x %{?**};
%define import_path	gitlab.com/gitlab-org/gitlab-ci-multi-runner

%description
This is the official GitLab Runner written in Go. It runs tests and
sends the results to GitLab. GitLab CI is the open-source continuous
integration service included with GitLab that coordinates the testing.

%prep
%setup -qc

# for doc
mv gitlab-ci-multi-runner-*/*.md .

# don't you love go?
install -d src/$(dirname %{import_path})
mv gitlab-ci-multi-runner-* src/%{import_path}
cd src/%{import_path}

mkdir -p out/docker
ln -s %{SOURCE1} out/docker
ln -s %{SOURCE2} out/docker
# touch, otherwise make rules would download it nevertheless
touch out/docker/prebuilt-*.tar.xz

# avoid docker being used even if executable found
cat <<'EOF' > docker
#!/bin/sh
echo >&2 "No docker"
exit 1
EOF
chmod a+rx docker

%build
# check that the revision is correct
#tar xvf out/docker/prebuilt.tar.gz repositories
#revision=$(sed -rne 's/.*"gitlab-runner-build":\{"([^"]+)":.*/\1/p' repositories)
#test "$revision" = %{revision}

export GOPATH=$(pwd)
cd src/%{import_path}
export PATH=$(pwd):$PATH

# build docker bindata. if you forget this, you get such error:
# executors/docker/executor_docker.go:180: undefined: Asset
%{__make} docker
%{__make} version | tee version.txt

CN=gitlab.com/gitlab-org/gitlab-ci-multi-runner/common
LDFLAGS="-X $CN.NAME=gitlab-ci-multi-runner -X $CN.VERSION=%{version} -X $CN.REVISION=%{revision}"
%gobuild

# verify that version matches
./gitlab-ci-multi-runner -v > v
v=$(awk '$1 == "Version:" {print $2}' v)
test "$v" = "%{version}"

%install
rm -rf $RPM_BUILD_ROOT
install -d $RPM_BUILD_ROOT{%{_sysconfdir}/gitlab-runner,%{_bindir},/var/lib/gitlab-runner/.gitlab-runner}

install -p src/%{import_path}/%{name} $RPM_BUILD_ROOT%{_bindir}/gitlab-runner

# backward compat name for previous pld packaging
ln -s gitlab-runner $RPM_BUILD_ROOT%{_bindir}/gitlab-ci-multi-runner

%clean
rm -rf $RPM_BUILD_ROOT

%pre
%groupadd -g 330 gitlab-runner
%useradd -u 330 -d /var/lib/gitlab-runner -g gitlab-runner -c "GitLab Runner" gitlab-runner

%postun
if [ "$1" = "0" ]; then
	%userremove gitlab-runner
	%groupremove gitlab-runner
fi

%files
%defattr(644,root,root,755)
%doc README.md CHANGELOG.md
%dir %attr(750,root,root) %{_sysconfdir}/gitlab-runner
%attr(755,root,root) %{_bindir}/gitlab-ci-multi-runner
%attr(755,root,root) %{_bindir}/gitlab-runner
%dir %attr(750,gitlab-runner,gitlab-runner) /var/lib/gitlab-runner
%dir %attr(750,gitlab-runner,gitlab-runner) /var/lib/gitlab-runner/.gitlab-runner
