package com.sonyericsson.permissiongen;

/**
 * Simple class to hold information about a single permission-entry in the AndroidManifest.xml file/files.
 * @author kenneth.andersson@sonyericsson.com
 */

class PermissionEntry {
    private String mPermissionName;
    private String mPermissionGroup;
    private String mProtectionLevel;
    private String mLabelTag;
    private String mDescriptionTag;
    private String mLabel;
    private String mDescription;

    public PermissionEntry(String permissionName, String permissionGroup, String protectionLevel, String labelTag, String descriptionTag) {
        mPermissionName = permissionName;
        mPermissionGroup = permissionGroup;
        mProtectionLevel = protectionLevel;
        int index = labelTag.indexOf("@string/");
        if (index != -1) {
            mLabelTag = labelTag.substring(index + "@string/".length());
        }
        index = descriptionTag.indexOf("@string/");
        if (index != -1) {
            mDescriptionTag = descriptionTag.substring(index + "@string/".length());
        }
    }

    public String getPermissionName() {
        return mPermissionName;
    }

    public String getPermissionGroup() {
        return mPermissionGroup;
    }

    public String getProtectionLevel() {
        return mProtectionLevel;
    }

    public String getLabel() {
        return mLabel;
    }

    public String getDescription() {
        return mDescription;
    }

    public String getLabelTag() {
        return mLabelTag;
    }

    public String getDescriptionTag() {
        return mDescriptionTag;
    }

    public void setLabel(String label) {
        mLabel = label;
    }

    public void setDescription(String description) {
        mDescription = description;
    }

    public String toString() {
        return "PermissionEntry [mDescription=" + mDescription + ", mLabel=" + mLabel
                + ", mPermissionGroup=" + mPermissionGroup + ", mPermissionName=" + mPermissionName
                + ", mProtectionLevel=" + mProtectionLevel + "]";
    }
}