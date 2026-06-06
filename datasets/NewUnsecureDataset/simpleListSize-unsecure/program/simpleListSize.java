public class simpleListSize {

    public static int listSizeLeak(int h) {
        int ret;
        if (h < 10) {
            ret = h;
        } else {
            ret = 10;
        }
        return ret;
    }

}
