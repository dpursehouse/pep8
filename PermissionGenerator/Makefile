SRC := $(wildcard src/com/sonyericsson/permissiongen/*.java)
EXE_PERMISSION_GENERATOR := PermissionGenerate.jar
JAVAC := javac
JAR := jar
MKDIR := mkdir -p

.PHONY : all bin compile clean

all : bin

bin : $(EXE_PERMISSION_GENERATOR)

compile : $(SRC)
	  $(MKDIR) bin
	  $(JAVAC) -g $(SRC) -d bin

$(EXE_PERMISSION_GENERATOR) : compile permissiongen_manifest.mf
			      $(JAR) cmf permissiongen_manifest.mf $@ -C bin .
			      chmod +x $@

clean :
	rm -fR bin $(EXE_PERMISSION_GENERATOR)